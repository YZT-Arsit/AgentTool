from __future__ import annotations

import hashlib
import math
import random
import time
from collections import Counter,defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean,pstdev

from .experiment import MultinomialNB,auc,svg_bar,write_csv
from .path_oram import PathORAM
from .stage2 import binary_eval,percentile,perm_binary,svg_scatter

VARIANTS=("MODULAR-ORAM","CANONICAL-MODULAR","UNIFIED-ORAM","UNIFIED-ORAM-PAD")
SYSTEMS=("GAAP-derived","PAuth-derived")
FORBIDDEN=("source_semantic_step","source_architecture_component","logical_id","record_key","is_dummy","hidden_state","private_label")

@dataclass(frozen=True)
class IndependentEpisode:
    entity:int; hidden_state:int; authorized:bool=True

def bid(store,key,n):return int.from_bytes(hashlib.sha256(f"{store}:{key}".encode()).digest()[:8],"big")%n
class ArchitectureStorage:
    def __init__(self,stores,variant,seed):
        self.stores=stores;self.variant=variant;self.unified="UNIFIED" in variant;self.dev_trace=[];self.host_trace=[];self.real=0;self.dummy=0;self.lat=[]
        if self.unified:
            total=sum(stores.values());self.offset={};off=0
            for s,n in stores.items():self.offset[s]=off;off+=n
            self.orams={"UNIFIED_ORAM":PathORAM(total,seed,4,math.ceil(math.log2(total)))}
        else:self.orams={s:PathORAM(n,seed+i*99991,4,math.ceil(math.log2(n))) for i,(s,n) in enumerate(stores.items())}
    def access(self,store,key,op,step,component,dummy=False):
        endpoint="UNIFIED_ORAM" if self.unified else store
        logical=(self.offset[store] if self.unified else 0)+bid(store,key,self.stores[store])
        start=time.perf_counter_ns();_,physical=self.orams[endpoint].access(logical,op,f"update:{key}" if op=="write" else None);self.lat.append((time.perf_counter_ns()-start)/1000)
        public={"store":endpoint,"operation":op,"order":len(self.host_trace),**physical};self.host_trace.append(public)
        self.dev_trace.append({**public,"source_semantic_step":step,"source_architecture_component":component,"record_key":key,"is_dummy":dummy})
        if dummy:self.dummy+=1
        else:self.real+=1
    def reset(self):
        h=self.host_trace;d=self.dev_trace;self.host_trace=[];self.dev_trace=[];return h,d

class DerivedMediator_GAAP:
    """Abstraction of GAAP's documented private DB, permission DB and disclosure log."""
    stores={"PRIVATE_DATA_DB":1024,"PERMISSION_DB":1024,"DISCLOSURE_LOG":2048}
    def __init__(self,variant,seed):self.variant=variant;self.storage=ArchitectureStorage(self.stores,variant,seed)
    def execute(self,e):
        s=self.storage;start=time.perf_counter_ns()
        if self.variant=="CANONICAL-MODULAR":
            s.access("PRIVATE_DATA_DB",f"DATA_{e.entity}" if e.hidden_state==0 else "DUMMY_DATA","read","resolve_private_value","private_data_db",e.hidden_state!=0)
            s.access("DISCLOSURE_LOG",f"PRIOR_{e.entity}" if e.hidden_state==1 else "DUMMY_PRIOR","read","recover_transitive_taint","disclosure_log",e.hidden_state!=1)
        elif e.hidden_state==0:s.access("PRIVATE_DATA_DB",f"DATA_{e.entity}","read","resolve_private_value","private_data_db")
        else:s.access("DISCLOSURE_LOG",f"PRIOR_{e.entity}","read","recover_transitive_taint","disclosure_log")
        s.access("PERMISSION_DB",f"PERMISSION_{e.entity}","read","check_external_disclosure","permission_database")
        if self.variant=="UNIFIED-ORAM-PAD":s.access("PRIVATE_DATA_DB","UNIFIED_PAD","read","fixed_budget_padding","experiment_padding",True)
        s.access("DISCLOSURE_LOG",f"DISCLOSURE_{e.entity}","write","record_disclosure","disclosure_log")
        allowed=e.authorized;payload=f"synthetic_private_value_{e.entity}";result={"authorized":allowed,"recipient":f"party_{e.entity}@example.invalid","payload":payload if allowed else None,"disclosure_recorded":True,"tool_outcome":"sent" if allowed else "denied"}
        host,dev=s.reset();return result,host,dev,(time.perf_counter_ns()-start)/1000

class DerivedMediator_PAuth:
    """Conservative PAuth abstraction: cached NL slice only; envelopes are inline values."""
    stores={"SLICE_STATE":1024}
    def __init__(self,variant,seed):self.variant=variant;self.storage=ArchitectureStorage(self.stores,variant,seed)
    def execute(self,e):
        s=self.storage;start=time.perf_counter_ns()
        s.access("SLICE_STATE",f"SLICE_{e.entity}","read","load_expected_operation","nl_slice")
        # Derived operands carry an inline signed-envelope witness. Verification
        # is trusted compute, not a fabricated persistent-store access.
        witness=hashlib.sha256(f"envelope:{e.entity}".encode()).digest() if e.hidden_state else b"literal"
        allowed=e.authorized and bool(witness);result={"authorized":allowed,"file":f"synthetic_file_{e.entity}","operand_origin":"verified" if e.hidden_state else "literal","tool_outcome":"shared" if allowed else "denied"}
        host,dev=s.reset();return result,host,dev,(time.perf_counter_ns()-start)/1000

MEDIATORS={"GAAP-derived":DerivedMediator_GAAP,"PAuth-derived":DerivedMediator_PAuth}

def episodes(n,seed,natural):
    rng=random.Random(seed);p=.30 if natural else .50;out=[]
    for _ in range(n):out.append(IndependentEpisode(rng.randrange(64),int(rng.random()<p),True))
    return out

def features(t,level):
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
    out += [f"leaf:{i}:{x['leaf']}" for i,x in enumerate(t)]
    return out

def binary_metrics(xs,ys,seed,train=None,test=None):
    if train is None:
        ids=list(range(len(ys)));random.Random(seed).shuffle(ids);cut=int(.7*len(ids));train,test=ids[:cut],ids[cut:]
    m=MultinomialNB().fit([xs[i] for i in train],[ys[i] for i in train]);actual=[ys[i] for i in test];scores=[];pred=[]
    for i in test:
        s=m.scores(xs[i]);d=s.get(1,-1e9)-s.get(0,-1e9);scores.append(d);pred.append(int(d>=0))
    acc=sum(a==b for a,b in zip(actual,pred))/len(actual);f1s=[]
    for c in (0,1):
        tp=sum(a==c and b==c for a,b in zip(actual,pred));fp=sum(a!=c and b==c for a,b in zip(actual,pred));fn=sum(a==c and b!=c for a,b in zip(actual,pred));f1s.append(0 if 2*tp+fp+fn==0 else 2*tp/(2*tp+fp+fn))
    return acc,mean(f1s),auc(scores,actual)

def audit_traces(root):
    rows=[]
    for system,cls in MEDIATORS.items():
        traces={}
        for hidden in (0,1):
            m=cls("MODULAR-ORAM",123);_,host,dev,_=m.execute(IndependentEpisode(7,hidden));traces[hidden]=(host,dev)
            for x in dev:
                rows.append(dict(system=system,hidden_state=hidden,order=x["order"],host_store=x["store"],operation=x["operation"],source_semantic_step=x["source_semantic_step"],source_architecture_component=x["source_architecture_component"]))
        a,b=traces[0][0],traces[1][0]
        rows.append(dict(system=system,hidden_state="AUDIT",order="",host_store="",operation="",source_semantic_step=f"count_changes={len(a)!=len(b)}; histogram_changes={Counter(x['store'] for x in a)!=Counter(x['store'] for x in b)}; order_changes={[x['store'] for x in a]!=[x['store'] for x in b]}",source_architecture_component="pre-classification audit"))
    write_csv(root/"results_stage4/DERIVED_TRACE_AUDIT.csv",rows);write_csv(root/"DERIVED_TRACE_AUDIT.csv",rows)

def summarize(rows):
    g=defaultdict(list);p=defaultdict(list)
    for r in rows:
        k=(r["system"],r["distribution"],r["variant"],r["feature"],r["split"],r["metric"]);g[k].append(float(r["value"]));p[k].append(float(r["permutation"]))
    out=[]
    for k,v in sorted(g.items()):out.append(dict(system=k[0],distribution=k[1],variant=k[2],feature=k[3],split=k[4],metric=k[5],mean=mean(v),std=pstdev(v),chance=.5,permutation_mean=mean(p[k]),permutation_std=pstdev(p[k])))
    return out

def run_stage4(root:Path,n=2400,seeds=(0,1,2)):
    audit_traces(root) # Written before any classifier is trained.
    raw=[];perf=[];config=[]
    for seed in seeds:
        for system,cls in MEDIATORS.items():
            for dist in ("balanced","natural"):
                eps=episodes(n,seed+(0 if dist=="balanced" else 5000),dist=="natural")
                for variant in VARIANTS:
                    m=cls(variant,seed*10007+71);traces=[];times=[];outputs=[]
                    for e in eps:
                        out,h,d,u=m.execute(e);outputs.append(out);traces.append(h);times.append(u)
                        for x in h:
                            if any(k in x for k in FORBIDDEN):raise AssertionError("development/private field exposed")
                    labels=[e.hidden_state for e in eps]
                    for f in ("F0","F1","F2","F3","F4","F5"):
                        xs=[features(t,f) for t in traces];acc,mf1,ra=binary_metrics(xs,labels,seed);pm=perm_binary(xs,labels,seed)
                        raw += [dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="random",metric="accuracy",value=acc,permutation=pm),dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="random",metric="macro_f1",value=mf1,permutation=pm),dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="random",metric="roc_auc",value=ra,permutation=pm)]
                        if dist=="balanced" and f=="F4":
                            tr=[i for i,e in enumerate(eps) if e.entity<48];te=[i for i,e in enumerate(eps) if e.entity>=48];ga,gf1,gauc=binary_metrics(xs,labels,seed,tr,te);sy=list(labels);random.Random(seed+811).shuffle(sy);gp=binary_metrics(xs,sy,seed,tr,te)[0]
                            raw += [dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="grouped_entity",metric="accuracy",value=ga,permutation=gp),dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="grouped_entity",metric="macro_f1",value=gf1,permutation=gp),dict(seed=seed,system=system,distribution=dist,variant=variant,feature=f,split="grouped_entity",metric="roc_auc",value=gauc,permutation=gp)]
                    st=[v for o in m.storage.orams.values() for v in o.stash_samples];physical=[sum(x["physical_blocks_transferred"] for x in t) for t in traces]
                    perf.append(dict(seed=seed,system=system,distribution=dist,variant=variant,logical_accesses=mean(map(len,traces)),physical_blocks=mean(physical),bandwidth_mib=mean(physical)*4096/1048576,tree_nodes=sum(len(o.tree) for o in m.storage.orams.values()),mean_latency_us=mean(times),p50_latency_us=percentile(times,.5),p95_latency_us=percentile(times,.95),mean_stash=mean(st),max_stash=max(o.max_stash for o in m.storage.orams.values()),dummy_fraction=m.storage.dummy/(m.storage.real+m.storage.dummy)))
    summary=summarize(raw);write_csv(root/"results_stage4/per_seed_results.csv",raw);write_csv(root/"results_stage4/summary.csv",summary);write_csv(root/"results_stage4/performance.csv",perf)
    config=[dict(system="GAAP-derived",source="arXiv:2604.19657v1",stores="PRIVATE_DATA_DB:1024;PERMISSION_DB:1024;DISCLOSURE_LOG:2048",block_bytes=4096,bucket_size=4,n=2400,seeds="0;1;2",natural_hidden_probability=.30),dict(system="PAuth-derived",source="arXiv:2603.17170v2",stores="SLICE_STATE:1024",block_bytes=4096,bucket_size=4,n=2400,seeds="0;1;2",natural_hidden_probability=.30)]
    write_csv(root/"results_stage4/configuration.csv",config)
    def val(system,variant,f="F4",dist="balanced",split="random"):return next(x["mean"] for x in summary if x["system"]==system and x["variant"]==variant and x["feature"]==f and x["distribution"]==dist and x["split"]==split and x["metric"]=="accuracy")
    for system in SYSTEMS:svg_bar(root/f"figures_stage4/{system.split('-')[0].lower()}_privacy.svg",f"{system} privacy",list(VARIANTS),[val(system,v) for v in VARIANTS],"Accuracy")
    svg_bar(root/"figures_stage4/gaap_feature_ladder.svg","GAAP-derived modular feature ladder",["F0","F1","F2","F3","F4","F5"],[val("GAAP-derived","MODULAR-ORAM",f) for f in ("F0","F1","F2","F3","F4","F5")],"Accuracy")
    compare=("CANONICAL-MODULAR","UNIFIED-ORAM","UNIFIED-ORAM-PAD");x=[mean(float(r["physical_blocks"]) for r in perf if r["system"]=="GAAP-derived" and r["distribution"]=="balanced" and r["variant"]==v) for v in compare]
    svg_scatter(root/"figures_stage4/gaap_privacy_overhead.svg",list(compare),x,[val("GAAP-derived",v) for v in compare])
    matrix=[
        dict(architecture="Stage-3 Reference Mediator",independent_source="no",multiple_persistent_states="yes",modular_trace_varies_naturally="yes",leakage_above_chance="yes",canonical_near_chance="yes",unified_near_chance="yes",modular_cost_advantage="yes in evaluated Stage-3 configs",evidence_category="reference"),
        dict(architecture="GAAP-derived",independent_source="arXiv:2604.19657v1",multiple_persistent_states="yes, documented",modular_trace_varies_naturally="yes under separate-store deployment",leakage_above_chance="yes",canonical_near_chance="yes",unified_near_chance="yes",modular_cost_advantage="no versus unpadded unified; yes versus unified-pad",evidence_category="POSITIVE with deployment assumption"),
        dict(architecture="PAuth-derived",independent_source="arXiv:2603.17170v2",multiple_persistent_states="not documented",modular_trace_varies_naturally="no",leakage_above_chance="no",canonical_near_chance="yes",unified_near_chance="yes",modular_cost_advantage="not applicable",evidence_category="NEGATIVE"),
    ];write_csv(root/"EXTERNAL_VALIDITY_MATRIX.csv",matrix)
    return summary,perf
