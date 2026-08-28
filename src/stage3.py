from __future__ import annotations

import csv
import hashlib
import math
import random
import time
from collections import Counter,defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean,pstdev
from typing import Any

from .experiment import MultinomialNB,auc,svg_bar,write_csv
from .path_oram import PathORAM
from .stage2 import binary_eval,percentile,perm_binary,svg_scatter

STORES=("OBJECT_STORE","POLICY_STORE","CREDENTIAL_STORE","HISTORY_STORE")
ARCHS=("MODULAR-V2","MODULAR-V2-PAD","MODULAR-V2-HIST","MODULAR-V3","V2-UNIFIED","V2-UNIFIED-PAD")
SMALL={"OBJECT_STORE":1024,"POLICY_STORE":1024,"CREDENTIAL_STORE":128,"HISTORY_STORE":2048}
MEDIUM={k:v*4 for k,v in SMALL.items()}
FORBIDDEN=("logical_id","block_id","record_key","record_type","is_dummy","private_mode","history_sensitive","recipient_id")

@dataclass(frozen=True)
class RealAction:
    recipient:int;content:int;attachment:int|None;sender_account:int|None;purpose:str="correspondence"

@dataclass
class Episode:
    action:RealAction; history_sensitive:bool

class MockEmailService:
    def send(self,args:dict[str,Any])->dict[str,Any]:
        return {"status":"sent","message_handle":"SYNTHETIC_MESSAGE_OK","authorized":True}

def private_value(store,key):
    if store=="OBJECT_STORE" and key.startswith("CONTACT_"):
        i=int(key.split("_")[-1]);return {"address":f"person_{i}@example.invalid","preflight_required":bool(i%2),"allowed":i%17!=16}
    if store=="OBJECT_STORE" and key.startswith("CONTENT_"):return {"text":f"synthetic_content_{key.split('_')[-1]}"}
    if store=="OBJECT_STORE" and key.startswith("DOCUMENT_"):return {"document":f"synthetic_document_{key.split('_')[-1]}"}
    if store=="OBJECT_STORE" and key.startswith("SENDER_"):
        i=int(key.split("_")[-1]);return {"sender":f"synthetic_account_{i}","account":i}
    if store=="POLICY_STORE":return {"allowed":not key.startswith("DENY_")}
    if store=="CREDENTIAL_STORE":return {"credential_semantics":f"synthetic_credential_profile_{key.split('_')[-1]}"}
    if store=="HISTORY_STORE":return {"synthetic_history":key}
    return {"dummy":"trusted-only"}

def stable_block(store,key,n):return int.from_bytes(hashlib.sha256(f"{store}:{key}".encode()).digest()[:8],"big")%n
class StorageBackend:
    def __init__(self,architecture,seed,sizes):
        self.architecture=architecture;self.unified="UNIFIED" in architecture;self.sizes=sizes
        if self.unified:
            total=sum(sizes.values());h=math.ceil(math.log2(total));self.orams={"UNIFIED_ORAM":PathORAM(total,seed,4,h)};self.offset={};off=0
            for s in STORES:self.offset[s]=off;off+=sizes[s]
        else:
            self.orams={s:PathORAM(sizes[s],seed+i*100003,4,math.ceil(math.log2(sizes[s]))) for i,s in enumerate(STORES)}
        self.trace=[];self.category_us=defaultdict(float);self.oram_us=[]
    def access(self,store,key,op="read"):
        if self.unified:
            endpoint="UNIFIED_ORAM";bid=self.offset[store]+stable_block(store,key,self.sizes[store])
        else:endpoint=store;bid=stable_block(store,key,self.sizes[store])
        start=time.perf_counter_ns();_,physical=self.orams[endpoint].access(bid,op,f"updated:{key}" if op=="write" else None);us=(time.perf_counter_ns()-start)/1000
        self.oram_us.append(us);self.category_us[store]+=us
        event={"store":endpoint,"operation":op,"order":len(self.trace),**physical}
        self.trace.append(event);return private_value(store,key)
    def pad(self,store,slot):self.access(store,f"DUMMY_SLOT_{slot}","read")

class ReferenceTrustedAgentMediator:
    """State-machine mediator; traces arise only through executed store methods."""
    def __init__(self,architecture,seed,sizes=SMALL):self.architecture=architecture;self.storage=StorageBackend(architecture,seed,sizes);self.tool=MockEmailService()
    def execute(self,e:Episode):
        a=e.action;start=time.perf_counter_ns();before=len(self.storage.trace)
        recipient=self.storage.access("OBJECT_STORE",f"CONTACT_{a.recipient}")
        authorized=recipient["allowed"]
        # Private recipient metadata requires authorization before further object
        # materialization; batch-safe recipients permit object gathering first.
        preflight=recipient["preflight_required"]
        if preflight:
            authorized &= self.storage.access("POLICY_STORE",f"RECIPIENT_POLICY_{a.recipient}")["allowed"]
        content=self.storage.access("OBJECT_STORE",f"CONTENT_{a.content}")
        attachment=None
        if a.attachment is not None:attachment=self.storage.access("OBJECT_STORE",f"DOCUMENT_{a.attachment}")["document"]
        account=a.sender_account if a.sender_account is not None else a.recipient%4
        sender=self.storage.access("OBJECT_STORE",f"SENDER_{account}")
        if not preflight:authorized &= self.storage.access("POLICY_STORE",f"RECIPIENT_POLICY_{a.recipient}")["allowed"]
        authorized &= self.storage.access("POLICY_STORE",f"PURPOSE_{a.purpose}")["allowed"]
        if a.attachment is not None:authorized &= self.storage.access("POLICY_STORE",f"ATTACHMENT_POLICY_{a.attachment}")["allowed"]
        authorized &= self.storage.access("POLICY_STORE",f"SENDER_POLICY_{account}")["allowed"]
        credential=self.storage.access("CREDENTIAL_STORE",f"CREDENTIAL_{account}")
        if e.history_sensitive:self.storage.access("HISTORY_STORE",f"DISCLOSURE_{a.recipient}")
        # Padding is inserted before the mandatory final audit write, preserving
        # operation placement and never changing authorization/tool semantics.
        used=self.storage.trace[before:]
        if self.architecture in ("MODULAR-V2-PAD","V2-UNIFIED-PAD"):
            for i in range(10-len(used)):self.storage.pad("OBJECT_STORE",i)
        elif self.architecture=="MODULAR-V2-HIST":
            counts=Counter(x["store"] for x in self.storage.trace[before:])
            targets={"OBJECT_STORE":4,"POLICY_STORE":4,"CREDENTIAL_STORE":1,"HISTORY_STORE":1}
            for store in STORES:
                for i in range(targets[store]-counts[store]):self.storage.pad(store,i)
        elif self.architecture=="MODULAR-V3":
            # Natural accesses above are semantically real. Canonical V3 is
            # executed by the dedicated method below, not padded post hoc.
            raise AssertionError("use execute_canonical")
        self.storage.access("HISTORY_STORE",f"AUDIT_{a.recipient}","write")
        args={"recipient":recipient["address"],"content":content["text"],"attachment":attachment,"sender":sender["sender"],"credential_semantics":credential["credential_semantics"],"authorized":authorized,"history_updated":True}
        outcome=self.tool.send(args) if authorized else {"status":"denied","message_handle":None,"authorized":False}
        trace=self.storage.trace[before:];return {**args,"tool_outcome":outcome},trace,(time.perf_counter_ns()-start)/1000
    def execute_canonical(self,e:Episode):
        a=e.action;start=time.perf_counter_ns();before=len(self.storage.trace);s=self.storage
        recipient=s.access("OBJECT_STORE",f"CONTACT_{a.recipient}");content=s.access("OBJECT_STORE",f"CONTENT_{a.content}")
        av=s.access("OBJECT_STORE",f"DOCUMENT_{a.attachment}") if a.attachment is not None else (s.pad("OBJECT_STORE","attachment") or {"document":None})
        account=a.sender_account if a.sender_account is not None else a.recipient%4;sender=s.access("OBJECT_STORE",f"SENDER_{account}")
        p1=s.access("POLICY_STORE",f"RECIPIENT_POLICY_{a.recipient}");p2=s.access("POLICY_STORE",f"PURPOSE_{a.purpose}")
        p3=s.access("POLICY_STORE",f"ATTACHMENT_POLICY_{a.attachment}") if a.attachment is not None else (s.pad("POLICY_STORE","attachment") or {"allowed":True})
        p4=s.access("POLICY_STORE",f"SENDER_POLICY_{account}");credential=s.access("CREDENTIAL_STORE",f"CREDENTIAL_{account}")
        if e.history_sensitive:s.access("HISTORY_STORE",f"DISCLOSURE_{a.recipient}")
        else:s.pad("HISTORY_STORE","disclosure")
        s.access("HISTORY_STORE",f"AUDIT_{a.recipient}","write")
        authorized=recipient["allowed"] and p1["allowed"] and p2["allowed"] and p3["allowed"] and p4["allowed"]
        args={"recipient":recipient["address"],"content":content["text"],"attachment":av["document"],"sender":sender["sender"],"credential_semantics":credential["credential_semantics"],"authorized":authorized,"history_updated":True}
        outcome=self.tool.send(args) if authorized else {"status":"denied","message_handle":None,"authorized":False}
        return {**args,"tool_outcome":outcome},s.trace[before:],(time.perf_counter_ns()-start)/1000

def execute_episode(m,e):return m.execute_canonical(e) if m.architecture=="MODULAR-V3" else m.execute(e)

def matched_episodes(n,seed):
    rng=random.Random(seed);out=[]
    # Full dependencies make count/store/op histograms identical; recipient
    # private metadata naturally selects preflight versus batch-safe ordering.
    for i in range(n):
        mode=i%2;choices=list(range(mode,16,2));r=rng.choice(choices)
        out.append(Episode(RealAction(r,rng.randrange(64),rng.randrange(64),rng.randrange(4)),True))
    rng.shuffle(out);return out

def natural_episodes(n,seed,history_probability=.15):
    rng=random.Random(seed);out=[]
    # Documented mixture: attachment 30%, explicit account 20%, history policy 15%.
    for _ in range(n):
        r=rng.randrange(16);out.append(Episode(RealAction(r,rng.randrange(64),rng.randrange(64) if rng.random()<.30 else None,rng.randrange(4) if rng.random()<.20 else None),rng.random()<history_probability))
    return out

def trace_features(t,level):
    stores=[x["store"] for x in t];events=[f"{x['store']}_{x['operation']}" for x in t];out=[f"len={len(t)}"]
    if level=="F0":return out
    out += [f"hist:{s}={stores.count(s)}" for s in sorted(set(stores))]
    if level=="F1":return out
    out += [f"sp:{i}:{s}" for i,s in enumerate(stores)]
    if level=="F2":return out
    out += [f"ep:{i}:{e}" for i,e in enumerate(events)]
    if level=="F3":return out
    for n in (1,2,3):out += [f"ng{n}:{'|'.join(events[i:i+n])}" for i in range(len(events)-n+1)]
    if level=="F4":return out
    out += [f"leaf:{i}:{x['leaf']}" for i,x in enumerate(t)]+[f"buckets:{x['buckets_touched']}" for x in t]
    return out

def timing_eval(values,labels,seed):
    ids=list(range(len(labels)));random.Random(seed).shuffle(ids);cut=int(.7*len(ids));tr,te=ids[:cut],ids[cut:]
    m0=mean(values[i] for i in tr if labels[i]==0);m1=mean(values[i] for i in tr if labels[i]==1);direction=1 if m1>=m0 else -1;scores=[direction*values[i] for i in te];actual=[labels[i] for i in te]
    threshold=(m0+m1)/2;pred=[int(direction*v>=direction*threshold) for v in (values[i] for i in te)]
    return sum(a==p for a,p in zip(actual,pred))/len(actual),auc(scores,actual)

def summarize(rows):
    groups=defaultdict(list);perms=defaultdict(list)
    for r in rows:
        k=(r["dataset"],r["architecture"],r["feature"],r["split"],r["metric"]);groups[k].append(float(r["value"]));perms[k].append(float(r["permutation"]))
    out=[]
    for k,v in sorted(groups.items()):out.append(dict(dataset=k[0],architecture=k[1],feature=k[2],split=k[3],metric=k[4],mean=mean(v),std=pstdev(v),chance=.5,permutation_mean=mean(perms[k]),permutation_std=pstdev(perms[k])))
    return out

def run_stage3(root:Path,n=2400,seeds=(0,1,2)):
    rows=[];timing=[];perf=[]
    for seed in seeds:
        datasets={"matched":matched_episodes(n,seed),"natural":natural_episodes(n,seed,.15),"natural_balanced":natural_episodes(n,seed+50000,.50)}
        for architecture in ARCHS:
            for dname,eps in datasets.items():
                m=ReferenceTrustedAgentMediator(architecture,seed*10007+31,SMALL);traces=[];times=[];outs=[]
                for e in eps:
                    out,t,us=execute_episode(m,e);outs.append(out);traces.append(t);times.append(us)
                    for ev in t:
                        if any(f in ev for f in FORBIDDEN):raise AssertionError("private trace field")
                labels=[(e.action.recipient%2) if dname=="matched" else int(e.history_sensitive) for e in eps]
                for f in ("F0","F1","F2","F3","F4","F5"):
                    xs=[trace_features(t,f) for t in traces];acc,ra=binary_eval(xs,labels,seed);perm=perm_binary(xs,labels,seed)
                    rows += [dict(seed=seed,dataset=dname,architecture=architecture,feature=f,split="random",metric="accuracy",value=acc,permutation=perm),dict(seed=seed,dataset=dname,architecture=architecture,feature=f,split="random",metric="roc_auc",value=ra,permutation=perm)]
                    if dname=="matched" and f=="F4":
                        train=[i for i,e in enumerate(eps) if e.action.recipient<12];test=[i for i,e in enumerate(eps) if e.action.recipient>=12];ga,gauc=binary_eval(xs,labels,seed,train,test)
                        # Grouped permutation is computed by shuffling labels globally then using the same groups.
                        sy=list(labels);random.Random(seed+811).shuffle(sy);gp=binary_eval(xs,sy,seed,train,test)[0]
                        rows += [dict(seed=seed,dataset=dname,architecture=architecture,feature=f,split="grouped_recipient",metric="accuracy",value=ga,permutation=gp),dict(seed=seed,dataset=dname,architecture=architecture,feature=f,split="grouped_recipient",metric="roc_auc",value=gauc,permutation=gp)]
                ta,tauc=timing_eval(times,labels,seed);timing.append(dict(seed=seed,dataset=dname,architecture=architecture,accuracy=ta,roc_auc=tauc,chance=.5,mean_total_us=mean(times),p50_total_us=percentile(times,.5),p95_total_us=percentile(times,.95),mean_oram_us=mean(m.storage.oram_us),policy_us_per_episode=m.storage.category_us["POLICY_STORE"]/n,credential_us_per_episode=m.storage.category_us["CREDENTIAL_STORE"]/n,history_us_per_episode=m.storage.category_us["HISTORY_STORE"]/n))
                if dname=="matched":
                    events=[x for t in traces for x in t];stash=[v for o in m.storage.orams.values() for v in o.stash_samples]
                    perf.append(dict(seed=seed,configuration="small",architecture=architecture,logical_accesses=mean(map(len,traces)),physical_blocks=mean(sum(x["physical_blocks_transferred"] for x in t) for t in traces),buckets=mean(sum(x["buckets_touched"] for x in t) for t in traces),bandwidth_mib=mean(sum(x["physical_blocks_transferred"] for x in t) for t in traces)*4096/1048576,mean_latency_us=mean(times),p95_latency_us=percentile(times,.95),mean_stash=mean(stash),max_stash=max(o.max_stash for o in m.storage.orams.values()),tree_nodes=sum(len(o.tree) for o in m.storage.orams.values()),max_path=max(x["buckets_touched"] for x in events)))
    # Small/medium architectural sensitivity on a short, identical action stream.
    sensitivity=[]
    for cname,sizes in (("small",SMALL),("medium",MEDIUM)):
        eps=matched_episodes(250,77)
        for arch in ("MODULAR-V3","V2-UNIFIED","V2-UNIFIED-PAD"):
            m=ReferenceTrustedAgentMediator(arch,919,sizes);ts=[];tr=[]
            for e in eps:
                _,t,u=execute_episode(m,e);ts.append(u);tr.append(t)
            sensitivity.append(dict(configuration=cname,architecture=arch,total_records=sum(sizes.values()),tree_nodes=sum(len(o.tree) for o in m.storage.orams.values()),max_path=max(x["buckets_touched"] for t in tr for x in t),physical_blocks=mean(sum(x["physical_blocks_transferred"] for x in t) for t in tr),mean_latency_us=mean(ts),p95_latency_us=percentile(ts,.95),max_stash=max(o.max_stash for o in m.storage.orams.values())))
    summary=summarize(rows)
    write_csv(root/"results_stage3/per_seed_privacy.csv",rows);write_csv(root/"results_stage3/privacy_summary.csv",summary);write_csv(root/"results_stage3/timing.csv",timing);write_csv(root/"results_stage3/performance.csv",perf);write_csv(root/"results_stage3/size_sensitivity.csv",sensitivity)
    def val(a,d="matched",f="F4",split="random"):return next(x["mean"] for x in summary if x["architecture"]==a and x["dataset"]==d and x["feature"]==f and x["split"]==split and x["metric"]=="accuracy")
    svg_bar(root/"figures_stage3/figure1_privacy_ladder.svg","Realistic mediator privacy ladder",list(ARCHS),[val(a) for a in ARCHS],"Accuracy")
    svg_bar(root/"figures_stage3/figure2_feature_source.svg","MODULAR-V2 feature source",["F0","F1","F2","F3","F4","F5"],[val("MODULAR-V2",f=f) for f in ("F0","F1","F2","F3","F4","F5")],"Accuracy")
    comp=("MODULAR-V3","V2-UNIFIED","V2-UNIFIED-PAD");x=[mean(float(r["physical_blocks"]) for r in perf if r["architecture"]==a) for a in comp]
    svg_scatter(root/"figures_stage3/figure3_privacy_overhead.svg",list(comp),x,[val(a) for a in comp])
    return summary,timing,perf,sensitivity
