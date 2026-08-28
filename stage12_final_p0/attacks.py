from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MaxAbsScaler


LEVELS = ("STRUCTURAL", "SIZE", "TIMING", "STRUCTURAL_SIZE", "STRUCTURAL_TIMING", "SIZE_TIMING", "ALL")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _truth(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["run_id"]: row for row in csv.DictReader(handle)}


def _features(row: dict[str, object], level: str) -> dict[str, float]:
    trace = row["host_visible_trace"]
    use_s = "STRUCTURAL" in level or level == "ALL"
    use_z = "SIZE" in level or level == "ALL"
    use_t = "TIMING" in level or level == "ALL"
    values: dict[str, float] = {}
    if use_s:
        ops = [str(event["operation_class"]) for event in trace]
        values["event_count"] = float(len(ops))
        values["sequence=" + "|".join(ops)] = 1.0
        for op, count in Counter(ops).items(): values[f"op={op}"] = float(count)
        for i in range(len(ops)-1): values[f"bigram={ops[i]}>{ops[i+1]}"] = values.get(f"bigram={ops[i]}>{ops[i+1]}",0)+1
        leaves = [int(event["physical_leaf"]) for event in trace if "physical_leaf" in event]
        values["oram_leaf_repeat"] = float(len(leaves)-len(set(leaves)))
    if use_z:
        sizes = [int(event["serialized_bytes"]) for event in trace]
        values["total_bytes"] = float(sum(sizes)); values["max_bytes"] = float(max(sizes, default=0))
        values["min_bytes"] = float(min(sizes, default=0)); values["unique_sizes"] = float(len(set(sizes)))
        values["size_sequence_hash"] = float(int(hashlib.sha256(json.dumps(sizes).encode()).hexdigest()[:8],16) % 100000)
    if use_t:
        offsets = [float(event["observed_offset_ms"]) for event in trace]
        gaps = []
        prior = 0.0
        for event in trace:
            offset = float(event["observed_offset_ms"])
            gaps.append(float(event.get("inter_event_ms", offset - prior)))
            prior = offset
        values["total_duration"] = offsets[-1] if offsets else 0.0
        values["mean_gap"] = mean(gaps) if gaps else 0.0
        values["max_gap"] = max(gaps, default=0.0)
        values["min_gap"] = min(gaps, default=0.0)
        values["gap_range"] = values["max_gap"] - values["min_gap"]
        values["burst_count"] = float(sum(g < .2 for g in gaps))
    return values


def _split(tasks: list[str], seed: int) -> tuple[set[str], set[str]]:
    unique = sorted(set(tasks)); random.Random(seed).shuffle(unique)
    cut = max(1, int(len(unique)*.7)); return set(unique[:cut]), set(unique[cut:])


def run_attacks(host_paths: list[Path], truth_paths: list[Path], output: Path, symbolic_output: Path) -> list[dict[str, object]]:
    rows=[]; labels={}
    for path in truth_paths: labels.update(_truth(path))
    for path in host_paths:
        for row in _read_jsonl(path):
            truth=labels[row["run_id"]]; row["_truth"]=truth; rows.append(row)
    results=[]; symbolic=[]
    runtimes=sorted({str(row["runtime"]) for row in rows})
    for runtime in runtimes:
        for family in ("AUTHORIZATION","PROVENANCE_HISTORY"):
            for variant in ("M0","M1","M2","M3"):
                subset=[row for row in rows if row["runtime"]==runtime and row["variant"]==variant and row["_truth"]["family"]==family]
                by_task={}
                for row in subset: by_task.setdefault(row["task_id"],{})[int(row["_truth"]["branch"])]=row
                shape_equal=all([e["operation_class"] for e in pair[0]["host_visible_trace"]]==[e["operation_class"] for e in pair[1]["host_visible_trace"]] for pair in by_task.values())
                size_equal=all([e["serialized_bytes"] for e in pair[0]["host_visible_trace"]]==[e["serialized_bytes"] for e in pair[1]["host_visible_trace"]] for pair in by_task.values())
                symbolic.append({"runtime":runtime,"family":family,"variant":variant,"structural_equal":shape_equal,"size_equal":size_equal,"pairs":len(by_task)})
                for level in LEVELS:
                    for seed in (0,1,2):
                        train_tasks,test_tasks=_split([str(row["task_id"]) for row in subset],seed)
                        train=[row for row in subset if row["task_id"] in train_tasks]; test=[row for row in subset if row["task_id"] in test_tasks]
                        train_x=[_features(row,level) for row in train]; test_x=[_features(row,level) for row in test]
                        train_y=np.array([int(row["_truth"]["branch"]) for row in train]); test_y=np.array([int(row["_truth"]["branch"]) for row in test])
                        vec=DictVectorizer(); x_train=vec.fit_transform(train_x); x_test=vec.transform(test_x)
                        models={"LogisticRegression":make_pipeline(MaxAbsScaler(),LogisticRegression(max_iter=2000,random_state=seed)),
                                "RandomForest":RandomForestClassifier(n_estimators=80,max_depth=8,random_state=seed,n_jobs=1)}
                        for model_name,model in models.items():
                            model.fit(x_train,train_y); prob=model.predict_proba(x_test)[:,1]; pred=(prob>=.5).astype(int)
                            # Empirical label-permutation null on the held-out
                            # predictions; ten per model/split (60 per aggregate)
                            # the small grouped test split around chance.
                            rng=np.random.default_rng(seed+991)
                            perm_auc=[]
                            for _ in range(10):
                                shuffled=test_y.copy(); rng.shuffle(shuffled)
                                perm_auc.append(roc_auc_score(shuffled,prob))
                            results.append({"runtime":runtime,"family":family,"variant":variant,"feature_set":level,
                                "model":model_name,"seed":seed,"accuracy":accuracy_score(test_y,pred),"auc":roc_auc_score(test_y,prob),
                                "permutation_auc":float(np.mean(perm_auc)),"chance":.5,"train_tasks":len(train_tasks),"test_tasks":len(test_tasks)})
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
    with symbolic_output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(symbolic[0])); writer.writeheader(); writer.writerows(symbolic)
    return results
