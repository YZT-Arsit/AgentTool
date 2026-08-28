from __future__ import annotations

import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Callable

from .simulator import Action, assert_public_trace, make_actions, mediate, occupancy, timed_mediation

VARIANTS = ("V0", "V1", "V2", "V3")

def tokens(trace: list[dict], mode: str = "full") -> list[str]:
    if mode == "count": return [f"length={len(trace)}"]
    out = [f"length={len(trace)}"]
    stores = [e["store"] for e in trace]
    if mode in ("store", "order", "full"):
        out += [f"store:{x}" for x in stores]
        out += [f"count:{s}={stores.count(s)}" for s in sorted(set(stores))]
    if mode in ("order", "full"):
        out += [f"pos:{i}:{e['store']}:{e['operation']}" for i, e in enumerate(trace)]
        out += [f"bigram:{a}>{b}" for a, b in zip(stores, stores[1:])]
    if mode == "full":
        for i, e in enumerate(trace):
            if "record_token" in e: out.append(f"addr:{i}:{e['record_token']}")
            if "path" in e: out += [f"path:{i}:{j}:{x}" for j, x in enumerate(e["path"])]
    return out

class MultinomialNB:
    def fit(self, xs: list[list[str]], ys: list[int]):
        self.labels = sorted(set(ys)); self.docs = Counter(ys); self.counts = defaultdict(Counter); self.totals = Counter()
        vocab = set()
        for x, y in zip(xs, ys):
            for t in x: self.counts[y][t] += 1; self.totals[y] += 1; vocab.add(t)
        self.v = len(vocab) + 1; self.n = len(ys); return self
    def scores(self, x: list[str]) -> dict[int, float]:
        result = {}
        for y in self.labels:
            s = math.log(self.docs[y] / self.n)
            denom = self.totals[y] + self.v
            for t in x: s += math.log((self.counts[y][t] + 1) / denom)
            result[y] = s
        return result
    def predict(self, x): return max(self.scores(x), key=self.scores(x).get)

def split_indices(n: int, seed: int) -> tuple[list[int], list[int]]:
    ids = list(range(n)); random.Random(seed).shuffle(ids); cut = int(.7*n); return ids[:cut], ids[cut:]

def multiclass(xs, ys, seed):
    train, test = split_indices(len(ys), seed)
    m = MultinomialNB().fit([xs[i] for i in train], [ys[i] for i in train])
    pred = [m.predict(xs[i]) for i in test]; actual = [ys[i] for i in test]
    acc = sum(a == b for a,b in zip(actual,pred))/len(test)
    f1s=[]
    for c in sorted(set(ys)):
        tp=sum(a==c and p==c for a,p in zip(actual,pred)); fp=sum(a!=c and p==c for a,p in zip(actual,pred)); fn=sum(a==c and p!=c for a,p in zip(actual,pred))
        f1s.append(0 if 2*tp+fp+fn==0 else 2*tp/(2*tp+fp+fn))
    return acc, mean(f1s)

def auc(scores, labels):
    pos=[s for s,y in zip(scores,labels) if y]; neg=[s for s,y in zip(scores,labels) if not y]
    wins=sum((a>b)+.5*(a==b) for a in pos for b in neg)
    return wins/(len(pos)*len(neg))

def binary(xs, ys, seed):
    train,test=split_indices(len(ys),seed); m=MultinomialNB().fit([xs[i] for i in train],[ys[i] for i in train])
    scores=[]; pred=[]; actual=[ys[i] for i in test]
    for i in test:
        sc=m.scores(xs[i]); delta=sc.get(1,-1e9)-sc.get(0,-1e9); scores.append(delta); pred.append(int(delta>=0))
    return sum(a==p for a,p in zip(actual,pred))/len(test), auc(scores,actual)

def shuffled_metric(xs, ys, seed, binary_task=False):
    shuffled=list(ys); random.Random(seed+991).shuffle(shuffled)
    return (binary if binary_task else multiclass)(xs,shuffled,seed)[1 if binary_task else 0]

def pair_linkability(traces, labels, seed):
    rng=random.Random(seed); xs=[]; ys=[]; by=defaultdict(list)
    for i,y in enumerate(labels): by[y].append(i)
    for _ in range(min(3000,len(traces))):
        same=rng.randrange(2)
        if same:
            y=rng.choice(list(by)); i,j=rng.sample(by[y],2)
        else:
            y,z=rng.sample(list(by),2); i=rng.choice(by[y]); j=rng.choice(by[z])
        a=traces[i]; b=traces[j]; ta=set(tokens(a)); tb=set(tokens(b))
        # Only host-visible equality/linkage features, no private identifiers.
        common=ta&tb
        xs.append([f"common:{t}" for t in common] + [f"overlap={min(10,len(common))}"])
        ys.append(same)
    return (*binary(xs,ys,seed), shuffled_metric(xs,ys,seed,True))

def write_csv(path: Path, rows: list[dict], fields=None):
    path.parent.mkdir(parents=True,exist_ok=True); fields=fields or list(rows[0])
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def svg_bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str, maxv=1.0):
    width,height=720,430; left,bottom=70,360; plotw=620; ploth=280
    colors=["#4C78A8","#F58518","#54A24B","#E45756"]
    bars=[]
    for i,(lab,val) in enumerate(zip(labels,values)):
        x=left+i*(plotw/len(labels))+25; bw=plotw/len(labels)-50; bh=ploth*val/maxv; y=bottom-bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{colors[i%4]}"/><text x="{x+bw/2:.1f}" y="{bottom+22}" text-anchor="middle">{lab}</text><text x="{x+bw/2:.1f}" y="{y-7:.1f}" text-anchor="middle">{val:.3f}</text>')
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><style>text{{font:14px sans-serif}} .title{{font:bold 18px sans-serif}}</style><text x="360" y="28" text-anchor="middle" class="title">{title}</text><line x1="{left}" y1="80" x2="{left}" y2="{bottom}" stroke="black"/><line x1="{left}" y1="{bottom}" x2="690" y2="{bottom}" stroke="black"/><text x="18" y="220" transform="rotate(-90 18 220)" text-anchor="middle">{ylabel}</text>{''.join(bars)}</svg>'''
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(svg,encoding="utf-8")

def run(root: Path, n=6000, seeds=(0,1,2)):
    rows=[]; overhead=[]; cache={}
    for seed in seeds:
        actions=make_actions(n,seed)
        for variant in VARIANTS:
            traces=[mediate(a,variant,seed*10_000_000+i).host_visible_trace for i,a in enumerate(actions)]
            for t in traces: assert_public_trace(t)
            cache[(seed,variant)]=(actions,traces)
            # Probe A uses fixed occupancy class as required.
            ids=[i for i,a in enumerate(actions) if occupancy(a)==3]; ax=[tokens(traces[i]) for i in ids]; ay=[actions[i].recipient for i in ids]
            acc,f1=multiclass(ax,ay,seed); sh=shuffled_metric(ax,ay,seed)
            rows.append(dict(seed=seed,variant=variant,probe="A_recipient_identity",metric="accuracy",value=acc,chance=1/16,shuffled=sh))
            rows.append(dict(seed=seed,variant=variant,probe="A_recipient_identity",metric="macro_f1",value=f1,chance=1/16,shuffled=sh))
            # Probe B
            bacc,bauc,bsh=pair_linkability(traces,[a.recipient for a in actions],seed)
            rows += [dict(seed=seed,variant=variant,probe="B_linkability",metric="accuracy",value=bacc,chance=.5,shuffled=bsh),dict(seed=seed,variant=variant,probe="B_linkability",metric="roc_auc",value=bauc,chance=.5,shuffled=bsh)]
            # Probe C
            cx=[tokens(t) for t in traces]; cy=[occupancy(a) for a in actions]; acc,f1=multiclass(cx,cy,seed); sh=shuffled_metric(cx,cy,seed)
            rows += [dict(seed=seed,variant=variant,probe="C_occupancy",metric="accuracy",value=acc,chance=.25,shuffled=sh),dict(seed=seed,variant=variant,probe="C_occupancy",metric="macro_f1",value=f1,chance=.25,shuffled=sh)]
            # Probe D: independent history relevance; manifests as optional read in V0-V2.
            dx=[tokens(t) for t in traces]; dy=[int(a.history_relevant) for a in actions]; acc,da=binary(dx,dy,seed); sh=shuffled_metric(dx,dy,seed,True)
            rows += [dict(seed=seed,variant=variant,probe="D_history_relevant",metric="accuracy",value=acc,chance=.5,shuffled=sh),dict(seed=seed,variant=variant,probe="D_history_relevant",metric="roc_auc",value=da,chance=.5,shuffled=sh)]
            us, accesses=timed_mediation(actions[:2000],variant,seed)
            overhead.append(dict(seed=seed,variant=variant,microseconds_per_action=us,visible_accesses=accesses,path_events=accesses*(6 if variant in ("V2","V3") else 1)))
        # V2 ablation, occupancy.
        actions,traces=cache[(seed,"V2")]; ys=[occupancy(a) for a in actions]
        for mode in ("count","store","order","full"):
            acc,f1=multiclass([tokens(t,mode) for t in traces],ys,seed); sh=shuffled_metric([tokens(t,mode) for t in traces],ys,seed)
            rows.append(dict(seed=seed,variant="V2",probe=f"C_ablation_{mode}",metric="accuracy",value=acc,chance=.25,shuffled=sh))
    write_csv(root/"results/per_seed_results.csv",rows); write_csv(root/"results/overhead.csv",overhead)
    groups=defaultdict(list); shuffled=defaultdict(list); chances={}
    for r in rows:
        k=(r["variant"],r["probe"],r["metric"]); groups[k].append(float(r["value"])); shuffled[k].append(float(r["shuffled"])); chances[k]=r["chance"]
    summary=[]
    for k,vals in sorted(groups.items()):
        summary.append(dict(variant=k[0],probe=k[1],metric=k[2],mean=mean(vals),std=pstdev(vals),chance=chances[k],shuffled_mean=mean(shuffled[k]),shuffled_std=pstdev(shuffled[k])))
    write_csv(root/"results/summary.csv",summary)
    def vals(probe,metric): return [next(r["mean"] for r in summary if r["variant"]==v and r["probe"]==probe and r["metric"]==metric) for v in VARIANTS]
    svg_bar(root/"figures/figure1_occupancy.svg","Optional-slot inference",list(VARIANTS),vals("C_occupancy","accuracy"),"Accuracy")
    svg_bar(root/"figures/figure2_linkability.svg","Same-recipient linkability",list(VARIANTS),vals("B_linkability","roc_auc"),"ROC-AUC")
    ov={v:mean(float(x["visible_accesses"]) for x in overhead if x["variant"]==v) for v in VARIANTS}
    svg_bar(root/"figures/figure3_access_overhead.svg","Host-visible access overhead",list(VARIANTS),[ov[v] for v in VARIANTS],"Accesses/action",max(ov.values())*1.1)
    return summary,overhead
