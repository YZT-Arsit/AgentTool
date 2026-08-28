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

from .experiment import MultinomialNB, auc, multiclass, shuffled_metric, svg_bar, write_csv
from .path_oram import PathORAM
from .simulator import Action, concrete

STORES=("OBJECT_STORE","POLICY_STORE","CREDENTIAL_STORE","HISTORY_STORE")
VARIANTS=("V2","V2-PAD","V2-HIST","V3")

@dataclass
class S2Episode:
    action: Action
    structural_class: int

def matched_episodes(n:int,seed:int)->list[S2Episode]:
    rng=random.Random(seed); out=[]
    for i in range(n):
        c=i%2
        out.append(S2Episode(Action("SEND_MESSAGE",rng.randrange(16),rng.randrange(32),rng.randrange(4),c,True),c))
    rng.shuffle(out); return out

def control_a_episodes(n:int,seed:int)->list[S2Episode]:
    """Equal total: attachment validation (O+P) vs account/history (C+H)."""
    rng=random.Random(seed); out=[]
    for i in range(n):
        c=i%2
        # Ground truth actions are used for semantics; the control schedule below
        # represents which additional dependency package private state activates.
        out.append(S2Episode(Action("SEND_MESSAGE",rng.randrange(16),rng.randrange(32) if c==0 else None,rng.randrange(4) if c else None,c,c==1),c))
    rng.shuffle(out); return out

def record_id(store:str,key:str,n_blocks:int)->int:
    return int.from_bytes(hashlib.sha256(f"{store}:{key}".encode()).digest()[:8],"big")%n_blocks

def structural_schedule(e:S2Episode)->list[tuple[str,str,str]]:
    a=e.action; r=f"CONTACT_{a.recipient}"; d=f"DOCUMENT_{a.attachment}"; ac=f"ACCOUNT_{a.explicit_account}"
    O="OBJECT_STORE"; P="POLICY_STORE"; C="CREDENTIAL_STORE"; H="HISTORY_STORE"
    if e.structural_class==0: # privacy policy requires just-in-time validation.
        return [(O,r,"read"),(P,f"RECIPIENT_POLICY_{r}","read"),(O,d,"read"),(P,f"DOCUMENT_POLICY_{d}","read"),(O,f"SENDER_{ac}","read"),(P,f"SENDER_POLICY_{ac}","read"),(C,ac,"read"),(H,f"HISTORY_{r}","read"),(H,f"AUDIT_{r}","write")]
    # Batch-safe policy allows object collection, then authorization checks.
    return [(O,r,"read"),(O,d,"read"),(O,f"SENDER_{ac}","read"),(C,ac,"read"),(P,f"RECIPIENT_POLICY_{r}","read"),(P,f"DOCUMENT_POLICY_{d}","read"),(P,f"SENDER_POLICY_{ac}","read"),(H,f"HISTORY_{r}","read"),(H,f"AUDIT_{r}","write")]

def control_a_schedule(e:S2Episode)->list[tuple[str,str,str]]:
    a=e.action; r=f"CONTACT_{a.recipient}"; O="OBJECT_STORE";P="POLICY_STORE";C="CREDENTIAL_STORE";H="HISTORY_STORE"
    base=[(O,r,"read"),(P,f"RECIPIENT_POLICY_{r}","read"),(O,"SENDER","read"),(P,"SENDER_POLICY","read"),(H,f"AUDIT_{r}","write")]
    if e.structural_class==0: return base[:-1]+[(O,f"DOC_{a.attachment}","read"),(P,f"DOC_POLICY_{a.attachment}","read")]+base[-1:]
    return base[:-1]+[(C,f"ACCOUNT_{a.explicit_account}","read"),(H,f"HISTORY_{r}","read")]+base[-1:]

CANONICAL=[("OBJECT_STORE","recipient","read"),("OBJECT_STORE","attachment","read"),("OBJECT_STORE","sender","read"),("CREDENTIAL_STORE","account","read"),("POLICY_STORE","recipient_policy","read"),("POLICY_STORE","attachment_policy","read"),("POLICY_STORE","sender_policy","read"),("HISTORY_STORE","history","read"),("HISTORY_STORE","audit","write")]

def canonical_schedule(e:S2Episode):
    """Canonical visible schedule while retaining the episode's real records."""
    rank={"OBJECT_STORE":0,"CREDENTIAL_STORE":1,"POLICY_STORE":2,"HISTORY_STORE":3}
    natural=structural_schedule(e)
    return sorted(natural,key=lambda x:(rank[x[0]],x[2]=="write",x[1]))

class ORAMMediator:
    def __init__(self,seed:int,n_blocks=128,z=4,height=7):
        self.n_blocks=n_blocks; self.orams={s:PathORAM(n_blocks,seed+i*100003,z,height) for i,s in enumerate(STORES)}
    def execute(self,e:S2Episode,variant:str,control_a=False):
        natural=control_a_schedule(e) if control_a else structural_schedule(e)
        if variant=="V3" and not control_a: schedule=canonical_schedule(e)
        else: schedule=list(natural)
        # PAD fixes total count only; HIST additionally fixes store histogram.
        # In the matched structural dataset both properties already match, so
        # these baselines deliberately preserve the natural sequence.
        target=9 if not control_a else 7
        if variant=="V2-PAD":
            while len(schedule)<target: schedule.append(("OBJECT_STORE",f"PAD_{len(schedule)}","read"))
        if variant=="V2-HIST":
            desired=Counter(s for s,_,_ in (CANONICAL if not control_a else schedule))
            have=Counter(s for s,_,_ in schedule)
            for s in STORES:
                for j in range(desired[s]-have[s]): schedule.append((s,f"HIST_PAD_{j}","read"))
        trace=[]; lat=[]
        for order,(store,key,op) in enumerate(schedule):
            bid=record_id(store,key,self.n_blocks); start=time.perf_counter_ns(); _,physical=self.orams[store].access(bid,op,f"value_{key}" if op=="write" else None); lat.append((time.perf_counter_ns()-start)/1000)
            trace.append({"store":store,"operation":op,"order":order,**physical})
        return concrete(e.action),trace,lat

def features(trace,level):
    stores=[x["store"] for x in trace]; events=[f"{x['store']}_{x['operation']}" for x in trace]
    out=[f"length={len(trace)}"]
    if level=="F0": return out
    out += [f"hist:{s}={stores.count(s)}" for s in STORES]
    if level=="F1": return out
    out += [f"storepos:{i}:{s}" for i,s in enumerate(stores)]
    if level=="F2": return out
    out += [f"eventpos:{i}:{x}" for i,x in enumerate(events)]
    if level=="F3": return out
    for n in (1,2,3): out += [f"ng{n}:{'|'.join(events[i:i+n])}" for i in range(len(events)-n+1)]
    if level=="F4": return out
    out += [f"leafpos:{i}:{x['leaf']}" for i,x in enumerate(trace)]
    out += [f"bucketcount:{x['buckets_touched']}" for x in trace]
    return out

def binary_eval(xs,ys,seed,train_ids=None,test_ids=None):
    if train_ids is None:
        ids=list(range(len(ys))); random.Random(seed).shuffle(ids); cut=int(.7*len(ids)); train_ids,test_ids=ids[:cut],ids[cut:]
    m=MultinomialNB().fit([xs[i] for i in train_ids],[ys[i] for i in train_ids]); actual=[ys[i] for i in test_ids]; scores=[];pred=[]
    for i in test_ids:
        s=m.scores(xs[i]); d=s.get(1,-1e9)-s.get(0,-1e9);scores.append(d);pred.append(int(d>=0))
    return sum(a==p for a,p in zip(actual,pred))/len(actual),auc(scores,actual)

def perm_binary(xs,ys,seed):
    y=list(ys);random.Random(seed+811).shuffle(y);return binary_eval(xs,y,seed)[0]

def linkability_eval(traces,labels,seed):
    rng=random.Random(seed);by=defaultdict(list)
    for i,y in enumerate(labels):by[y].append(i)
    xs=[];ys=[]
    for _ in range(2400):
        same=rng.randrange(2)
        if same:
            y=rng.choice(list(by));i,j=rng.sample(by[y],2)
        else:
            y,z=rng.sample(list(by),2);i=rng.choice(by[y]);j=rng.choice(by[z])
        a=traces[i];b=traces[j]
        # Equality and co-occurrence of legitimately visible physical endpoints.
        toks=[]
        for p,(x,y) in enumerate(zip(a,b)):
            toks.append(f"same_leaf:{p}:{int(x['leaf']==y['leaf'])}")
            toks.append(f"leaf_pair:{p}:{min(x['leaf'],y['leaf'])}:{max(x['leaf'],y['leaf'])}")
        xs.append(toks);ys.append(same)
    acc,rauc=binary_eval(xs,ys,seed);return acc,rauc,perm_binary(xs,ys,seed)

def percentile(vals,p):
    v=sorted(vals);return v[min(len(v)-1,int((len(v)-1)*p))]

def svg_scatter(path:Path,labels,xvals,yvals):
    w,h=720,430;left,bottom=85,350;pw,ph=570,260
    xmin,xmax=min(xvals)-1,max(xvals)+1;ymin,ymax=0.45,1.05;colors=("#4C78A8","#F58518","#54A24B","#E45756")
    pts=[]
    for i,(lab,x,y) in enumerate(zip(labels,xvals,yvals)):
        # Small display jitter only when physical costs are identical; values in labels remain exact.
        px=left+pw*((x-xmin)/(xmax-xmin))+(i-1.5)*7;py=bottom-ph*((y-ymin)/(ymax-ymin))
        pts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{colors[i%len(colors)]}"/><text x="{px+10:.1f}" y="{py-8:.1f}">{lab}: ({x:.0f}, {y:.3f})</text>')
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="white"/><style>text{{font:14px sans-serif}} .title{{font:bold 18px sans-serif}}</style><text x="360" y="28" text-anchor="middle" class="title">Privacy / physical-overhead tradeoff</text><line x1="{left}" y1="90" x2="{left}" y2="{bottom}" stroke="black"/><line x1="{left}" y1="{bottom}" x2="655" y2="{bottom}" stroke="black"/><text x="370" y="400" text-anchor="middle">Physical blocks transferred / action</text><text x="20" y="220" transform="rotate(-90 20 220)" text-anchor="middle">Hidden-state accuracy</text><line x1="{left}" y1="{bottom-ph*((.5-ymin)/(ymax-ymin))}" x2="655" y2="{bottom-ph*((.5-ymin)/(ymax-ymin))}" stroke="#777" stroke-dasharray="5 5"/>{''.join(pts)}</svg>'''
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(svg,encoding="utf-8")

def run_stage2(root:Path,n=3000,seeds=(0,1,2)):
    rows=[]; overhead=[]; identity=[]; control_a_rows=[]
    for seed in seeds:
        eps=matched_episodes(n,seed)
        for variant in VARIANTS:
            med=ORAMMediator(seed*1009+17); traces=[]; latencies=[]; totals=[]
            start=time.perf_counter()
            for e in eps:
                _out,t,l=med.execute(e,variant);traces.append(t);latencies+=l;totals.append(len(t))
            total_us=(time.perf_counter()-start)*1e6/n
            ys=[e.structural_class for e in eps]
            for level in ("F0","F1","F2","F3","F4","F5"):
                xs=[features(t,level) for t in traces];acc,rauc=binary_eval(xs,ys,seed);perm=perm_binary(xs,ys,seed)
                rows.append(dict(seed=seed,variant=variant,control="equal_count_store_operation",feature=level,split="random",accuracy=acc,roc_auc=rauc,chance=.5,permutation=perm))
                if level in ("F3","F5"):
                    train=[i for i,e in enumerate(eps) if e.action.recipient<12];test=[i for i,e in enumerate(eps) if e.action.recipient>=12]
                    ga,gauc=binary_eval(xs,ys,seed,train,test)
                    rows.append(dict(seed=seed,variant=variant,control="equal_count_store_operation",feature=level,split="grouped_recipient",accuracy=ga,roc_auc=gauc,chance=.5,permutation=""))
            paths=sum(len(t) for t in traces); buckets=sum(x["buckets_touched"] for t in traces for x in t); blocks=sum(x["physical_blocks_transferred"] for t in traces for x in t)
            stash_samples=[v for o in med.orams.values() for v in o.stash_samples]
            overhead.append(dict(seed=seed,variant=variant,n_blocks=128,bucket_size=4,height=7,logical_accesses=mean(totals),physical_path_reads=paths/n,physical_buckets=buckets/n,physical_blocks=blocks/n,bandwidth_mib=blocks/n*4096/(1024*1024),mean_stash=mean(stash_samples),max_stash=max(o.max_stash for o in med.orams.values()),mean_oram_us=mean(latencies),p50_oram_us=percentile(latencies,.5),p95_oram_us=percentile(latencies,.95),mean_mediation_us=total_us))
        # Equal-total control A under V2/V3 (V3 canonical for the public leakage class is represented by a fixed seven-event schedule).
        ca=control_a_episodes(n,seed)
        for variant in ("V2","V2-PAD"):
            med=ORAMMediator(seed*2003+9);tr=[]
            for e in ca: tr.append(med.execute(e,variant,True)[1])
            ys=[e.structural_class for e in ca]
            for level in ("F0","F1","F2"):
                acc,aa=binary_eval([features(t,level) for t in tr],ys,seed)
                control_a_rows.append(dict(seed=seed,variant=variant,control="equal_total",feature=level,accuracy=acc,roc_auc=aa,chance=.5,permutation=perm_binary([features(t,level) for t in tr],ys,seed)))
        # Address privacy using fixed class/schedule and recipients.
        med=ORAMMediator(seed*3001+4);tr=[]
        for e in eps: tr.append(med.execute(e,"V2")[1])
        xs=[features(t,"F5") for t in tr];ys=[e.action.recipient for e in eps];acc,f1=multiclass(xs,ys,seed)
        identity.append(dict(seed=seed,probe="recipient_identity",accuracy=acc,macro_f1=f1,roc_auc="",chance=1/16,permutation=shuffled_metric(xs,ys,seed)))
        lacc,lauc,lperm=linkability_eval(tr,[e.action.recipient for e in eps],seed)
        identity.append(dict(seed=seed,probe="same_recipient_linkability",accuracy=lacc,macro_f1="",roc_auc=lauc,chance=.5,permutation=lperm))
    write_csv(root/"results_stage2/structural_results.csv",rows);write_csv(root/"results_stage2/equal_count_control.csv",control_a_rows);write_csv(root/"results_stage2/identity_results.csv",identity);write_csv(root/"results_stage2/overhead.csv",overhead)
    # Sensitivity: correctness/overhead snapshots, not classifier cherry-picking.
    sensitivity=[]
    for nb,z,h in ((64,4,6),(128,4,7),(128,5,7)):
        med=ORAMMediator(404,nb,z,h);eps=matched_episodes(400,404);l=[]
        for e in eps: l.append(len(med.execute(e,"V2")[1]))
        sensitivity.append(dict(n_blocks=nb,bucket_size=z,height=h,logical_accesses=mean(l),mean_stash=mean(o.mean_stash for o in med.orams.values()),max_stash=max(o.max_stash for o in med.orams.values())))
    write_csv(root/"results_stage2/oram_sensitivity.csv",sensitivity)
    # Summaries.
    summary=[];groups=defaultdict(list)
    for r in rows:
        for metric in ("accuracy","roc_auc"):
            groups[(r["variant"],r["control"],r["feature"],r["split"],metric)].append(float(r[metric]))
    for k,v in sorted(groups.items()):
        matching=[r for r in rows if (r["variant"],r["control"],r["feature"],r["split"])==k[:4] and r["permutation"]!=""]
        pv=[float(r["permutation"]) for r in matching]
        summary.append(dict(variant=k[0],control=k[1],feature=k[2],split=k[3],metric=k[4],mean=mean(v),std=pstdev(v),chance=.5,permutation_mean=mean(pv) if pv else "",permutation_std=pstdev(pv) if pv else ""))
    write_csv(root/"results_stage2/summary.csv",summary)
    def val(v,f="F4"):return next(x["mean"] for x in summary if x["variant"]==v and x["feature"]==f and x["split"]=="random" and x["metric"]=="accuracy")
    svg_bar(root/"figures_stage2/figure_a_privacy_ladder.svg","Privacy ladder: matched structural state",list(VARIANTS),[val(v) for v in VARIANTS],"Accuracy")
    svg_bar(root/"figures_stage2/figure_b_feature_ladder.svg","V2 matched-control feature ladder",["F0","F1","F2","F3","F4","F5"],[val("V2",f) for f in ("F0","F1","F2","F3","F4","F5")],"Accuracy")
    ov={v:mean(float(x["physical_blocks"]) for x in overhead if x["variant"]==v) for v in VARIANTS}
    svg_scatter(root/"figures_stage2/figure_c_privacy_overhead.svg",list(VARIANTS),[ov[v] for v in VARIANTS],[val(v) for v in VARIANTS])
    return summary,overhead,identity,control_a_rows,sensitivity
