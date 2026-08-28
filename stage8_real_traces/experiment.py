from __future__ import annotations

import csv
import json
import random
import time
from collections import Counter,defaultdict
from pathlib import Path
from statistics import mean,pstdev

from src.experiment import svg_bar,write_csv
from src.stage4 import binary_metrics
from .runtime import FORBIDDEN,TASKS,VARIANTS,Episode,ServiceCluster,SourceFaithfulMediator,TraceTransport,generate_episode,ground_truth

def features(trace,full=False):
    endpoints=[x["destination_service"] for x in trace];ops=[x["operation_class"] for x in trace]
    events=[f"{a}:{b}" for a,b in zip(endpoints,ops)]
    out=[f"length={len(trace)}"]
    out += [f"endpoint_count:{k}={v}" for k,v in sorted(Counter(endpoints).items())]
    out += [f"position:{i}:{event}" for i,event in enumerate(events)]
    for n in (1,2,3):out += [f"ngram{n}:{'|'.join(events[i:i+n])}" for i in range(len(events)-n+1)]
    if full:
        out += [f"request_bin:{i}:{x['request_bytes']//32}" for i,x in enumerate(trace)]
        out += [f"response_bin:{i}:{x['response_bytes']//32}" for i,x in enumerate(trace)]
        out += [f"timing_bin:{i}:{min(20,int(x['duration_us']//250))}" for i,x in enumerate(trace)]
        out += [f"path:{i}:{x['physical_path']}" for i,x in enumerate(trace) if "physical_path" in x]
        out += [f"address:{i}:{x['stable_address']}" for i,x in enumerate(trace) if "stable_address" in x]
    return out

def split_indices(rows,kind):
    if kind=="grouped_entity":return ([i for i,r in enumerate(rows) if r["truth"]["entity"]<64],[i for i,r in enumerate(rows) if r["truth"]["entity"]>=64])
    if kind=="cross_policy":return ([i for i,r in enumerate(rows) if r["truth"]["policy_profile"]<3],[i for i,r in enumerate(rows) if r["truth"]["policy_profile"]>=3])
    if kind=="cross_task":return ([i for i,r in enumerate(rows) if r["truth"]["action_type"]=="SEND_MESSAGE"],[i for i,r in enumerate(rows) if r["truth"]["action_type"]=="SHARE_DOCUMENT"])
    raise ValueError(kind)

def evaluate(rows,label,seed,analysis,variant,splits):
    out=[]
    ys=[int(r["truth"][label]) for r in rows]
    for level in ("SYMBOLIC","FULL"):
        xs=[features(r["trace"],level=="FULL") for r in rows]
        for split in splits:
            train,test=split_indices(rows,split)
            if not train or not test or len(set(ys[i] for i in train))<2 or len(set(ys[i] for i in test))<2:continue
            acc,f1,ra=binary_metrics(xs,ys,seed,train,test)
            perm=[]
            for repeat in range(32):
                shuffled=list(ys);random.Random(seed*1009+8803+repeat).shuffle(shuffled)
                perm.append(binary_metrics(xs,shuffled,seed,train,test))
            pa,pf,pauc=(mean(x[i] for x in perm) for i in range(3))
            for metric,value,perm in (("accuracy",acc,pa),("macro_f1",f1,pf),("roc_auc",ra,pauc)):
                out.append(dict(seed=seed,analysis=analysis,secret=label,variant=variant,feature_level=level,split=split,metric=metric,value=value,chance=.5,permutation=perm))
    return out

def analyze_saved(root:Path):
    """Recompute inference/permutation controls without recapturing RPC traces."""
    root=Path(root);truth={}
    with (root/"stage8_real_traces/private_ground_truth.csv").open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key in ("seed","episode_id","entity","project","policy_profile","requires_history","permission_missing","prior_disclosure"):row[key]=int(row[key])
            truth[(row["seed"],row["episode_id"])]=row
    traces=defaultdict(list)
    with (root/"stage8_real_traces/raw_host_traces.jsonl").open(encoding="utf-8") as f:
        for line in f:
            event=json.loads(line);key=(int(event.pop("seed")),event.pop("variant"),int(event.pop("episode_id")));traces[key].append(event)
    all_eval=[]
    for seed in sorted({k[0] for k in traces}):
        for variant in VARIANTS:
            rows=[{"seed":seed,"episode_id":eid,"truth":truth[(seed,eid)],"trace":trace} for (s,v,eid),trace in traces.items() if s==seed and v==variant]
            mediation=[]
            for r in rows:
                if r["truth"]["initial_permission"]=="ALLOW" and r["truth"]["action_type"] in ("SEND_MESSAGE","SHARE_DOCUMENT"):
                    mediation.append({**r,"trace":[x for x in r["trace"] if x["action_index"]==0]})
            dynamic=[r for r in rows if r["truth"]["initial_permission"]=="ALLOW" or (r["truth"]["initial_permission"]=="MISSING" and r["truth"]["consent"]=="ALLOW")]
            all_eval += evaluate(mediation,"requires_history",seed,"mediation_only",variant,("grouped_entity","cross_policy","cross_task"))
            all_eval += evaluate(dynamic,"permission_missing",seed,"full_trajectory",variant,("grouped_entity","cross_policy"))
    summary=summarize(all_eval);write_csv(root/"results_stage8/per_seed_inference.csv",all_eval);write_csv(root/"results_stage8/inference_summary.csv",summary);return summary

def summarize(rows):
    groups=defaultdict(list);perms=defaultdict(list)
    keys=("analysis","secret","variant","feature_level","split","metric")
    for r in rows:
        k=tuple(r[x] for x in keys);groups[k].append(float(r["value"]));perms[k].append(float(r["permutation"]))
    return [{**dict(zip(keys,k)),"mean":mean(v),"std":pstdev(v),"chance":.5,"permutation_mean":mean(perms[k]),"permutation_std":pstdev(perms[k])} for k,v in sorted(groups.items())]

def signature(trace):return ">".join(f"{x['destination_service']}:{x['operation_class']}" for x in trace)

def symbolic_rows(dataset):
    out=[]
    for variant,rows in dataset.items():
        for analysis,label,selected in (
            ("mediation_only","requires_history",[r for r in rows if r["truth"]["initial_permission"]=="ALLOW" and r["truth"]["action_type"] in ("SEND_MESSAGE","SHARE_DOCUMENT")]),
            ("full_trajectory","permission_missing",[r for r in rows if (r["truth"]["initial_permission"]=="ALLOW" or (r["truth"]["initial_permission"]=="MISSING" and r["truth"]["consent"]=="ALLOW"))])):
            if analysis=="mediation_only":traces=[(r,[x for x in r["trace"] if x["action_index"]==0]) for r in selected]
            else:traces=[(r,r["trace"]) for r in selected]
            sets={c:{signature(t) for r,t in traces if int(r["truth"][label])==c} for c in (0,1)}
            lengths={c:[len(t) for r,t in traces if int(r["truth"][label])==c] for c in (0,1)}
            bytes_={c:[sum(x["request_bytes"]+x["response_bytes"] for x in t) for r,t in traces if int(r["truth"][label])==c] for c in (0,1)}
            timing={c:[sum(x["duration_us"] for x in t) for r,t in traces if int(r["truth"][label])==c] for c in (0,1)}
            overlap=len(sets[0]&sets[1])/max(1,len(sets[0]|sets[1]))
            out.append(dict(analysis=analysis,secret=label,variant=variant,class0_n=len(lengths[0]),class1_n=len(lengths[1]),
                            class0_mean_events=mean(lengths[0]),class1_mean_events=mean(lengths[1]),
                            class0_mean_bytes=mean(bytes_[0]),class1_mean_bytes=mean(bytes_[1]),
                            class0_mean_duration_us=mean(timing[0]),class1_mean_duration_us=mean(timing[1]),
                            class0_unique_sequences=len(sets[0]),class1_unique_sequences=len(sets[1]),sequence_jaccard=overlap,
                            deterministic_shape_distinction=sets[0].isdisjoint(sets[1])))
    return out

def run_stage8(root:Path,n_per_seed=320,seeds=(0,1,2)):
    root=Path(root);(root/"stage8_real_traces").mkdir(exist_ok=True);(root/"results_stage8").mkdir(exist_ok=True);(root/"figures_stage8").mkdir(exist_ok=True)
    raw_path=root/"stage8_real_traces/raw_host_traces.jsonl";gt_rows=[];generation=[];all_eval=[];functional=[];overhead=[];dataset_all={v:[] for v in VARIANTS}
    start=time.perf_counter()
    with raw_path.open("w",encoding="utf-8") as raw,ServiceCluster() as cluster:
        for seed in seeds:
            rng=random.Random(seed+20260825);episodes=[generate_episode(rng,i) for i in range(n_per_seed)]
            for e in episodes:
                expected=None;captured=[]
                for vi,variant in enumerate(VARIANTS):
                    transport=TraceTransport(cluster,variant,seed*100000+e.episode_id*31+vi);output,trace=SourceFaithfulMediator(variant,transport).execute(e)
                    if expected is None:expected=output
                    functional.append({"seed":seed,"episode_id":e.episode_id,"variant":variant,"matches_original":output==expected,"authorized":output["authorized"],"effect_count":output["effect_count"],"attempts":output["attempts"]})
                    for event in trace:
                        if any(k in event for k in FORBIDDEN):raise AssertionError("private field in host trace")
                        raw.write(json.dumps({"seed":seed,"episode_id":e.episode_id,"variant":variant,**event},sort_keys=True,separators=(",",":"))+"\n")
                    captured.append((variant,output,trace))
                # Ground truth is deliberately materialized only after every
                # variant has executed and its host trace has been captured.
                truth=ground_truth(e);gt_rows.append({"seed":seed,**truth});generation.append({"seed":seed,"episode_id":e.episode_id,"step_1":e.generation_order[0],"step_2":e.generation_order[1],"step_3":"execute_and_capture","step_4":"derive_labels","label_derived_after_execution":True})
                for variant,output,trace in captured:
                    dataset_all[variant].append({"seed":seed,"episode_id":e.episode_id,"truth":truth,"trace":trace,"output":output})
            # Evaluate each seed separately.
            for variant in VARIANTS:
                rows=[r for r in dataset_all[variant] if r["seed"]==seed]
                mediation=[]
                for r in rows:
                    if r["truth"]["initial_permission"]=="ALLOW" and r["truth"]["action_type"] in ("SEND_MESSAGE","SHARE_DOCUMENT"):
                        mediation.append({**r,"trace":[x for x in r["trace"] if x["action_index"]==0]})
                dynamic=[r for r in rows if r["truth"]["initial_permission"]=="ALLOW" or (r["truth"]["initial_permission"]=="MISSING" and r["truth"]["consent"]=="ALLOW")]
                all_eval += evaluate(mediation,"requires_history",seed,"mediation_only",variant,("grouped_entity","cross_policy","cross_task"))
                all_eval += evaluate(dynamic,"permission_missing",seed,"full_trajectory",variant,("grouped_entity","cross_policy"))
    for variant,rows in dataset_all.items():
        overhead.append(dict(variant=variant,episodes=len(rows),mean_actions=mean(r["output"]["attempts"] for r in rows),mean_host_events=mean(len(r["trace"]) for r in rows),
                             mean_wire_bytes=mean(sum(x["request_bytes"]+x["response_bytes"] for x in r["trace"]) for r in rows),
                             mean_observed_duration_us=mean(sum(x["duration_us"] for x in r["trace"]) for r in rows)))
    symbolic=symbolic_rows(dataset_all);summary=summarize(all_eval)
    write_csv(root/"stage8_real_traces/private_ground_truth.csv",gt_rows);write_csv(root/"results_stage8/generation_order_audit.csv",generation);write_csv(root/"results_stage8/functional_equivalence.csv",functional)
    write_csv(root/"results_stage8/per_seed_inference.csv",all_eval);write_csv(root/"results_stage8/inference_summary.csv",summary);write_csv(root/"results_stage8/symbolic_distinguishability.csv",symbolic);write_csv(root/"results_stage8/overhead.csv",overhead)
    # Figures use grouped/cross-task AUC only and are intentionally plain.
    def metric(analysis,variant,split):
        vals=[r["mean"] for r in summary if r["analysis"]==analysis and r["variant"]==variant and r["feature_level"]=="SYMBOLIC" and r["split"]==split and r["metric"]=="roc_auc"]
        return vals[0] if vals else .5
    svg_bar(root/"figures_stage8/mediation_cross_entity_auc.svg","Mediation-only provenance leakage",list(VARIANTS),[metric("mediation_only",v,"grouped_entity") for v in VARIANTS],"ROC-AUC")
    svg_bar(root/"figures_stage8/cross_task_auc.svg","SEND_MESSAGE to SHARE_DOCUMENT transfer",list(VARIANTS),[metric("mediation_only",v,"cross_task") for v in VARIANTS],"ROC-AUC")
    svg_bar(root/"figures_stage8/adaptive_trajectory_auc.svg","Adaptive policy-state leakage",list(VARIANTS),[metric("full_trajectory",v,"grouped_entity") for v in VARIANTS],"ROC-AUC")
    return {"summary":summary,"symbolic":symbolic,"overhead":overhead,"functional":functional,"elapsed_s":time.perf_counter()-start}
