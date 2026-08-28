from __future__ import annotations

import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def _episode_rows(path: Path) -> dict[int, list[dict[str, object]]]:
    groups: dict[int, list[dict[str, object]]] = {}
    for row in jsonl(path / "host_visible_trace.jsonl"):
        groups.setdefault(int(row["episode_token"]), []).append(row)
    for rows in groups.values(): rows.sort(key=lambda row: int(row["slot"]))
    return groups


def gateway_features(rows: list[dict[str, object]], ablation: str = "ALL") -> np.ndarray:
    scheduled = np.array([int(row["cloud_request_scheduled_ns"]) for row in rows], dtype=np.float64)
    request_send = np.array([int(row["cloud_request_send_ns"]) for row in rows], dtype=np.float64)
    gateway_receive = np.array([int(row["gateway_request_receive_ns"]) for row in rows], dtype=np.float64)
    response_scheduled = np.array([int(row["gateway_response_scheduled_ns"]) for row in rows], dtype=np.float64)
    response_send = np.array([int(row["gateway_response_send_ns"]) for row in rows], dtype=np.float64)
    cloud_receive = np.array([int(row["cloud_response_receive_ns"]) for row in rows], dtype=np.float64)
    fields = {
        "REQUEST_SLIP": (request_send - scheduled) / 1e6,
        "REQUEST_INGRESS": (gateway_receive - request_send) / 1e6,
        "RESPONSE_SLIP": (response_send - response_scheduled) / 1e6,
        "RESPONSE_EGRESS": (cloud_receive - response_send) / 1e6,
        "ROUND_TRIP": (cloud_receive - request_send) / 1e6,
        "INTER_REQUEST": np.diff(request_send) / 1e6,
        "INTER_RESPONSE": np.diff(cloud_receive) / 1e6,
        "SESSION_RELATIVE": np.concatenate(((request_send-request_send[0])/1e6,
                                             (cloud_receive-request_send[0])/1e6)),
        "ABSOLUTE_PHASE": np.array([(int(request_send[0]) % 1_000_000_000) / 1e6]),
    }
    selected = fields.values() if ablation == "ALL" else (fields[ablation],)
    values = np.concatenate(tuple(selected))
    summaries = np.array([float(np.mean(values)), float(np.std(values)), float(np.max(values)),
                          float(np.quantile(values, .95))])
    return np.concatenate((values, summaries))


def gateway_dataset(path: Path, family: str, ablation: str = "ALL") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    traces = _episode_rows(path)
    truth = [row for row in csv_rows(path / "private_ground_truth.csv") if row["family"] == family]
    X = np.vstack([gateway_features(traces[int(row["episode_token"])], ablation) for row in truth])
    return X, np.array([row["label"] for row in truth]), np.array([row["episode_token"] for row in truth])


def pir_episode_dataset(path: Path, profiles: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    trace = jsonl(path / "server_visible_trace.jsonl")
    private = csv_rows(path / "private_queries.csv")
    by_episode: dict[str, list[int]] = {}
    for index, row in enumerate(private): by_episode.setdefault(row["episode"], []).append(index)
    X=[]; y=[]; groups=[]
    for episode, positions in by_episode.items():
        label = private[positions[0]]["class"].split(":", 1)[0]
        if label not in profiles: continue
        rows = [trace[index] for index in positions]
        scheduled = np.array([int(row["scheduled_ns"]) for row in rows], dtype=np.float64)
        arrival = np.array([int(row["request_arrival_ns"]) for row in rows], dtype=np.float64)
        ready = np.array([int(row["answer_ready_ns"]) for row in rows], dtype=np.float64)
        slip=(arrival-scheduled)/1e6; answer=(ready-arrival)/1e6; gaps=np.diff(arrival)/1e6
        values=np.concatenate((slip,answer,gaps,[slip.mean(),slip.std(),answer.mean(),answer.std()]))
        X.append(values);y.append(label);groups.append(episode)
    return np.vstack(X),np.array(y),np.array(groups)


def pir_query_pair_dataset(path: Path, samples: int, seed: int, mode: str = "ALL") -> tuple[np.ndarray, np.ndarray]:
    trace=jsonl(path/"server_visible_trace.jsonl"); private=csv_rows(path/"private_queries.csv")
    eligible=[i for i,row in enumerate(private) if row["class"].startswith("M")]
    rng=random.Random(seed);features=[];labels=[]
    def row_feature(i:int)->np.ndarray:
        row=trace[i]
        values={"REQUEST_SLIP":(int(row["request_arrival_ns"])-int(row["scheduled_ns"]))/1e6,
                "ANSWER_DURATION":(int(row["answer_ready_ns"])-int(row["request_arrival_ns"]))/1e6}
        return np.array([values["REQUEST_SLIP"],values["ANSWER_DURATION"]] if mode=="ALL" else [values[mode]])
    by_target:dict[int,list[int]]={}
    for i in eligible:by_target.setdefault(int(private[i]["index"]),[]).append(i)
    targets=[target for target,values in by_target.items() if len(values)>1]
    for _ in range(samples//2):
        target=rng.choice(targets);a,b=rng.sample(by_target[target],2);features.append(abs(row_feature(a)-row_feature(b)));labels.append(1)
        left,right=rng.sample(targets,2);a=rng.choice(by_target[left]);b=rng.choice(by_target[right]);features.append(abs(row_feature(a)-row_feature(b)));labels.append(0)
    return np.vstack(features),np.array(labels)


def _models(seed: int):
    return {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed)),
        "RandomForest": RandomForestClassifier(n_estimators=120, max_depth=8, random_state=seed, n_jobs=1),
    }


def _bootstrap_binary(y: np.ndarray, pred: np.ndarray, seed: int, rounds: int = 200) -> tuple[float,float]:
    rng=np.random.default_rng(seed);scores=[]
    for _ in range(rounds):
        index=rng.integers(0,len(y),len(y))
        if len(np.unique(y[index]))==2:scores.append(roc_auc_score(y[index],pred[index]))
    return tuple(float(value) for value in np.quantile(scores,[.025,.975]))


def binary_holdout(name: str, Xdev: np.ndarray, ydev: np.ndarray, Xtest: np.ndarray, ytest: np.ndarray,
                   seed: int = 44) -> list[dict[str, object]]:
    rows=[]
    for model_name,model in _models(seed).items():
        fitted=clone(model).fit(Xdev,ydev);pred=fitted.predict_proba(Xtest)[:,list(fitted.classes_).index(1)]
        score=float(roc_auc_score(ytest,pred));low,high=_bootstrap_binary(ytest,pred,seed)
        rng=np.random.default_rng(seed+91);perms=[]
        observed_adv=abs(score-.5)
        for _ in range(200):perms.append(abs(float(roc_auc_score(rng.permutation(ytest),pred))-.5))
        p=(1+sum(value>=observed_adv for value in perms))/(len(perms)+1)
        rows.append({"attack":name,"model":model_name,"metric":"AUC","score":score,"ci_low":low,"ci_high":high,
                     "permutation_baseline":.5+float(np.mean(perms)),"permutation_p_value":p,"samples":len(ytest),
                     "chance":.5,"accept":score<=.55 and low<=.5<=high and p>.05})
    return rows


def multiclass_holdout(name: str, Xdev: np.ndarray, ydev: np.ndarray, Xtest: np.ndarray, ytest: np.ndarray,
                       seed: int = 55) -> list[dict[str, object]]:
    rows=[];chance=1/len(np.unique(ytest));rng=np.random.default_rng(seed+71)
    for model_name,model in _models(seed).items():
        fitted=clone(model).fit(Xdev,ydev);pred=fitted.predict(Xtest)
        score=float(accuracy_score(ytest,pred));macro=float(f1_score(ytest,pred,average="macro"));boots=[]
        for _ in range(200):
            index=rng.integers(0,len(ytest),len(ytest));boots.append(accuracy_score(ytest[index],pred[index]))
        low,high=(float(v) for v in np.quantile(boots,[.025,.975]));perms=[]
        for _ in range(200):perms.append(accuracy_score(rng.permutation(ytest),pred))
        p=(1+sum(value>=score for value in perms))/(len(perms)+1)
        rows.append({"attack":name,"model":model_name,"metric":"TOP1","score":score,"macro_f1":macro,
                     "ci_low":low,"ci_high":high,"permutation_baseline":float(np.mean(perms)),
                     "permutation_p_value":p,"samples":len(ytest),"chance":chance,
                     "confusion_matrix":json.dumps([[int(np.sum((ytest==a)&(pred==b))) for b in sorted(set(ytest))]
                                                    for a in sorted(set(ytest))]),
                     "accept":score<=chance+.05 and low<=chance<=high and p>.05})
    return rows


def select_binary(X: np.ndarray, y: np.ndarray, left: str, right: str) -> tuple[np.ndarray,np.ndarray]:
    mask=np.isin(y,[left,right]);return X[mask],(y[mask]==right).astype(int)


def cross_validated_binary(name:str,X:np.ndarray,y:np.ndarray,seed:int=67)->list[dict[str,object]]:
    rng=np.random.default_rng(seed);indices=np.arange(len(y));rng.shuffle(indices);folds=np.array_split(indices,4);rows=[]
    for model_name,base in _models(seed).items():
        pred=np.zeros(len(y))
        for fold in folds:
            train=np.setdiff1d(indices,fold);model=clone(base).fit(X[train],y[train]);pred[fold]=model.predict_proba(X[fold])[:,1]
        score=float(roc_auc_score(y,pred));low,high=_bootstrap_binary(y,pred,seed);perms=[]
        for _ in range(200):perms.append(abs(float(roc_auc_score(rng.permutation(y),pred))-.5))
        p=(1+sum(value>=abs(score-.5) for value in perms))/(len(perms)+1)
        rows.append({"attack":name,"model":model_name,"metric":"AUC","score":score,"ci_low":low,"ci_high":high,
                     "permutation_baseline":.5+float(np.mean(perms)),"permutation_p_value":p,"samples":len(y),
                     "chance":.5,"accept":score<=.55 and low<=.5<=high and p>.05})
    return rows


def aggregate_overhead(results: Path) -> list[dict[str, object]]:
    rows=[]
    for folder in sorted(path for path in results.iterdir() if path.is_dir() and (path/"host_visible_trace.jsonl").exists()):
        if folder.name.startswith("smoke") or folder.name in {"confirmatory_single","confirmatory_tool_sequences"}:
            continue
        trace=jsonl(folder/"host_visible_trace.jsonl");truth=csv_rows(folder/"private_ground_truth.csv")
        private=jsonl(folder/"gateway_private_instrumentation.jsonl")
        tokens={int(row["episode_token"]) for row in truth};durations=[];queue=[];slips=[]
        for token in tokens:
            values=sorted((row for row in trace if int(row["episode_token"])==token),key=lambda row:int(row["slot"]))
            durations.append((int(values[-1]["cloud_response_receive_ns"])-int(values[0]["cloud_request_send_ns"]))/1e6)
            slips.extend((int(row["gateway_response_send_ns"])-int(row["gateway_response_scheduled_ns"]))/1e6 for row in values)
        host_by_slot={(int(row["episode_token"]),int(row["slot"])):row for row in trace}
        releases={(int(row["episode_token"]),int(row["slot"])) for row in private if row.get("private_response_kind")=="REAL_RESULT"}
        completions={int(row["episode_token"]):int(row["private_completed_ns"]) for row in private if "private_completed_ns" in row}
        for token,completed in completions.items():
            candidates=[int(host_by_slot[key]["gateway_response_send_ns"]) for key in releases if key[0]==token and int(host_by_slot[key]["gateway_response_send_ns"])>=completed]
            if candidates:queue.append((min(candidates)-completed)/1e6)
        metrics=json.loads((folder/"process_metrics.json").read_text(encoding="utf-8"))
        real_heavy=sum(int(row["real_heavy_ops"]) for row in truth);slots=len(trace)
        rows.append({"experiment":folder.name,"episodes":len(tokens),"fixed_frames_each_direction":slots,
                     "bandwidth_bytes":slots*2*int(trace[0]["request_bytes"]),"mean_latency_ms":statistics.mean(durations),
                     "median_latency_ms":statistics.median(durations),"p95_latency_ms":float(np.quantile(durations,.95)),
                     "response_slip_mean_ms":statistics.mean(slips),"response_slip_p95_ms":float(np.quantile(slips,.95)),
                     "cloud_pacer_cpu_seconds":metrics["cloud_pacer"]["cpu_seconds"],
                     "gateway_cpu_seconds":metrics["gateway"]["cpu_seconds"],
                     "client_peak_memory_bytes":metrics["cloud_pacer"]["peak_working_set_bytes"],
                     "gateway_peak_memory_bytes":metrics["gateway"]["peak_working_set_bytes"],
                     "completion_to_release_mean_ms":statistics.mean(queue) if queue else "NA",
                     "completion_to_release_p95_ms":float(np.quantile(queue,.95)) if queue else "NA",
                     "real_heavy_ops":real_heavy,"dummy_heavy_ops":0,"action_slot_utilization":real_heavy/slots,
                     "real_result_frame_fraction":len(releases)/slots})
    for name in ("development_pir","confirmatory_pir"):
        folder=results/name
        if not (folder/"metrics.json").exists():continue
        metrics=json.loads((folder/"metrics.json").read_text(encoding="utf-8"));profile=json.loads((folder/"timing_profile.json").read_text(encoding="utf-8"))
        trace=jsonl(folder/"server_visible_trace.jsonl");episodes=len({row["episode"] for row in csv_rows(folder/"private_queries.csv")})
        durations=[]
        for episode in {row["episode"] for row in csv_rows(folder/"private_queries.csv")}:
            indices=[i for i,row in enumerate(csv_rows(folder/"private_queries.csv")) if row["episode"]==episode]
            durations.append((int(trace[indices[-1]]["answer_ready_ns"])-int(trace[indices[0]]["request_arrival_ns"]))/1e6)
        rows.append({"experiment":name,"episodes":episodes,"PIR_queries":metrics["queries"],
                     "PIR_queries_per_session":metrics["queries"]/episodes,"additional_dummy_PIR_queries":profile["dummy_queries"],
                     "bandwidth_bytes":metrics["queries"]*(metrics["online_upload_bytes"]+metrics["online_download_bytes"]),
                     "mean_latency_ms":statistics.mean(durations),"median_latency_ms":statistics.median(durations),
                     "p95_latency_ms":float(np.quantile(durations,.95)),"response_slip_mean_ms":"NA","response_slip_p95_ms":"NA",
                     "cloud_pacer_cpu_seconds":"NOT_MEASURED_SEPARATELY","gateway_cpu_seconds":"NOT_MEASURED_SEPARATELY",
                     "client_peak_memory_bytes":metrics["persistent_client_state_bytes"],"gateway_peak_memory_bytes":metrics["peak_allocated_bytes"],
                     "completion_to_release_mean_ms":"NA","completion_to_release_p95_ms":"NA",
                     "real_heavy_ops":0,"dummy_heavy_ops":0,"action_slot_utilization":"NA","real_result_frame_fraction":"NA"})
    return rows
