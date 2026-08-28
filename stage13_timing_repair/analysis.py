from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MaxAbsScaler


LAYERS=("READY_TIME","QUEUE_DELAY","RELEASE_SLIP","RELEASE_TO_SEND","SEND_TO_RECEIVE",
        "RECEIVER_ARRIVAL","RECEIVER_PROCESS","COMMIT_TIME","STRUCTURAL","SIZE","ALL_OBSERVER")


def _load_jsonl(path:Path)->list[dict[str,Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _load_truth(path:Path)->dict[str,dict[str,str]]:
    with path.open(encoding="utf-8",newline="") as handle:return {row["run_id"]:row for row in csv.DictReader(handle)}


def load_runs(results:Path)->list[dict[str,Any]]:
    runs=[]
    for stem in ("runtime1","runtime2"):
        truth=_load_truth(results/f"{stem}_truth.csv")
        private={row["run_id"]:row for row in _load_jsonl(results/f"{stem}_private_instrumentation.jsonl")}
        for row in _load_jsonl(results/f"{stem}_final_host.jsonl"):
            row["_truth"]=truth[row["run_id"]];row["_private"]=private[row["run_id"]];runs.append(row)
    return runs


def features(run:dict[str,Any],layer:str)->dict[str,float]:
    trace=run["host_visible_trace"]; private=run["_private"]; f={}
    if layer=="READY_TIME":
        durations=[(e["t1"]-e["t0"])/1e6 for e in private["private_instrumentation"]]
        f.update({"work_count":len(durations),"ready_total":sum(durations),"ready_max":max(durations,default=0)})
    elif layer=="QUEUE_DELAY":
        delays=[(e["t2"]-e["t1"])/1e6 for e in private["private_instrumentation"]]
        f.update({"queue_count":len(delays),"queue_total":sum(delays),"queue_max":max(delays,default=0)})
    elif layer=="RELEASE_SLIP":
        values=[e["release_slip_us"] for e in trace]
        f.update({f"slip_{i}":v for i,v in enumerate(values)});f.update({"slip_mean":mean(values),"slip_max":max(values)})
    elif layer=="RELEASE_TO_SEND":
        values=[e["send_offset_ms"]-e["release_offset_ms"] for e in trace]
        f.update({f"r2s_{i}":v for i,v in enumerate(values)});f["r2s_total"]=sum(values)
    elif layer=="SEND_TO_RECEIVE":
        values=[e["arrival_offset_ms"]-e["send_offset_ms"] for e in trace]
        f.update({f"s2r_{i}":v for i,v in enumerate(values)});f["s2r_total"]=sum(values)
    elif layer=="RECEIVER_ARRIVAL":
        arrivals=[e["arrival_offset_ms"] for e in trace];gaps=[arrivals[0]]+[b-a for a,b in zip(arrivals,arrivals[1:])]
        f.update({f"arrival_{i}":v for i,v in enumerate(arrivals)});f.update({f"gap_{i}":v for i,v in enumerate(gaps)})
        f.update({"arrival_total":arrivals[-1],"gap_range":max(gaps)-min(gaps),"gap_jitter":float(np.std(gaps))})
    elif layer=="RECEIVER_PROCESS":
        values=[e["receiver_start_offset_ms"]-e["arrival_offset_ms"] for e in trace]
        f.update({f"recvproc_{i}":v for i,v in enumerate(values)});f["recvproc_total"]=sum(values)
    elif layer=="COMMIT_TIME":
        f["commit_offset"]=max(e["commit_offset_ms"] for e in trace)
    elif layer=="STRUCTURAL":
        f["event_count"]=len(trace);f["oram_access_count"]=sum(e["oram_access_count"] for e in trace)
        f["sequence_fixed"]=float(all(e["slot"]==i+1 for i,e in enumerate(trace)))
        leaves=[leaf for e in trace for leaf in e["oram_physical_leaves"]]
        f["leaf_repeat"]=len(leaves)-len(set(leaves))
    elif layer=="SIZE":
        sizes=[e["receiver_bytes"] for e in trace];f.update({"total_bytes":sum(sizes),"unique_sizes":len(set(sizes)),"max_size":max(sizes)})
    elif layer=="ALL_OBSERVER":
        f.update(features(run,"STRUCTURAL"));f.update(features(run,"SIZE"));f.update(features(run,"RELEASE_SLIP"));
        f.update(features(run,"RECEIVER_ARRIVAL"));f.update(features(run,"COMMIT_TIME"))
    else:raise ValueError(layer)
    return {key:float(value) for key,value in f.items()}


def _models(seed:int):
    return {"LogisticRegression":make_pipeline(MaxAbsScaler(),LogisticRegression(max_iter=2000,random_state=seed)),
            "RandomForest":RandomForestClassifier(n_estimators=40,max_depth=8,random_state=seed,n_jobs=1)}


def _effective_auc(y:np.ndarray,p:np.ndarray)->float:
    # Direction is learned from training labels; do not flip after observing
    # final-test labels. This matches the predeclared one-sided AUC <= .55 gate.
    return float(roc_auc_score(y,p))


def _statistics(y:np.ndarray,p:np.ndarray,groups:np.ndarray,seed:int)->tuple[float,float,float,float,float]:
    observed=_effective_auc(y,p);rng=np.random.default_rng(seed+771)
    unique=np.unique(groups);boot=[]
    for _ in range(50):
        chosen=rng.choice(unique,size=len(unique),replace=True);indices=np.concatenate([np.flatnonzero(groups==g) for g in chosen])
        if len(np.unique(y[indices]))==2:boot.append(_effective_auc(y[indices],p[indices]))
    ci_low,ci_high=np.quantile(boot,[.025,.975])
    perm=[]
    for _ in range(50):
        shuffled=y.copy()
        for group in unique:
            idx=np.flatnonzero(groups==group);shuffled[idx]=rng.permutation(shuffled[idx])
        perm.append(_effective_auc(shuffled,p))
    pvalue=(1+sum(value>=observed for value in perm))/(len(perm)+1)
    return observed,float(ci_low),float(ci_high),float(np.mean(perm)),float(pvalue)


def grouped_attack(rows:list[dict[str,Any]],layer:str,model_name:str,seed:int=0)->dict[str,Any]:
    x=[features(row,layer) for row in rows];y=np.array([int(row["_truth"]["branch"]) for row in rows]);groups=np.array([row["task_id"] for row in rows])
    vec=DictVectorizer();matrix=vec.fit_transform(x);pred=np.zeros(len(rows));folds=GroupKFold(n_splits=4)
    for fold,(train,test) in enumerate(folds.split(matrix,y,groups)):
        model=_models(seed+fold)[model_name];model.fit(matrix[train],y[train]);pred[test]=model.predict_proba(matrix[test])[:,1]
    auc,low,high,perm,pvalue=_statistics(y,pred,groups,seed)
    return {"mean_auc":auc,"ci_low":low,"ci_high":high,"permutation_baseline":perm,"permutation_p_value":pvalue,
            "episodes":len(rows),"tasks":len(set(groups)),"split":"GROUPED_TASK_4FOLD"}


def within_task_attack(rows:list[dict[str,Any]],layer:str,model_name:str,seed:int=0)->dict[str,Any]:
    train=[row for row in rows if int(row["repetition"])<2];test=[row for row in rows if int(row["repetition"])==2]
    vec=DictVectorizer();xtrain=vec.fit_transform([features(row,layer) for row in train]);xtest=vec.transform([features(row,layer) for row in test])
    ytrain=np.array([int(row["_truth"]["branch"]) for row in train]);ytest=np.array([int(row["_truth"]["branch"]) for row in test])
    model=_models(seed)[model_name];model.fit(xtrain,ytrain);pred=model.predict_proba(xtest)[:,1]
    groups=np.array([row["task_id"] for row in test]);auc,low,high,perm,pvalue=_statistics(ytest,pred,groups,seed)
    return {"mean_auc":auc,"ci_low":low,"ci_high":high,"permutation_baseline":perm,"permutation_p_value":pvalue,
            "episodes":len(test),"tasks":len(set(groups)),"split":"WITHIN_TASK_REPETITION_HOLDOUT"}


def run_attacks(results_dir:Path,output:Path,cross_output:Path)->list[dict[str,Any]]:
    runs=load_runs(results_dir);out=[]
    runtimes=sorted({row["runtime"] for row in runs})
    for runtime in runtimes:
        for family in ("AUTHORIZATION","PROVENANCE_HISTORY","POOLED"):
            for variant in ("M2","M3"):
                rows=[row for row in runs if row["runtime"]==runtime and row["variant"]==variant and
                      (family=="POOLED" or row["_truth"]["family"]==family)]
                for layer in LAYERS:
                    for model in ("LogisticRegression","RandomForest"):
                        for evaluator in (grouped_attack,within_task_attack):
                            metric=evaluator(rows,layer,model)
                            out.append({"runtime":runtime,"family":family,"variant":variant,"feature_set":layer,"model":model,**metric})
    with output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
    cross=[]
    for source,target in ((runtimes[0],runtimes[1]),(runtimes[1],runtimes[0])):
        for layer in ("RELEASE_SLIP","RECEIVER_ARRIVAL","COMMIT_TIME","ALL_OBSERVER"):
            train=[r for r in runs if r["runtime"]==source and r["variant"]=="M3"]
            test=[r for r in runs if r["runtime"]==target and r["variant"]=="M3"]
            for model_name in ("LogisticRegression","RandomForest"):
                vec=DictVectorizer();xt=vec.fit_transform([features(r,layer) for r in train]);xv=vec.transform([features(r,layer) for r in test])
                yt=np.array([int(r["_truth"]["branch"]) for r in train]);yv=np.array([int(r["_truth"]["branch"]) for r in test])
                model=_models(42)[model_name];model.fit(xt,yt);pred=model.predict_proba(xv)[:,1]
                cross.append({"train_runtime":source,"test_runtime":target,"feature_set":layer,"model":model_name,
                              "auc":_effective_auc(yv,pred),"episodes":len(test)})
    with cross_output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(cross[0]));writer.writeheader();writer.writerows(cross)
    return out
