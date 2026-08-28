from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import numpy as np

from timing_closure.analysis import (
    aggregate_overhead,
    binary_holdout,
    cross_validated_binary,
    gateway_dataset,
    gateway_features,
    jsonl,
    multiclass_holdout,
    pir_episode_dataset,
    pir_query_pair_dataset,
    select_binary,
    write_csv,
)


def _pair_gateway(path: Path, family: str) -> tuple[np.ndarray,np.ndarray]:
    traces={}
    for row in jsonl(path/"host_visible_trace.jsonl"):
        traces.setdefault(int(row["episode_token"]),[]).append(row)
    with (path/"private_ground_truth.csv").open(encoding="utf-8",newline="") as handle:
        truth=[row for row in csv.DictReader(handle) if row["family"]==family]
    features={int(row["episode_token"]):gateway_features(sorted(traces[int(row["episode_token"])],key=lambda item:int(item["slot"])))
              for row in truth};labels={int(row["episode_token"]):row["label"] for row in truth}
    X=[];y=[];tokens=sorted(features)
    for i,left in enumerate(tokens):
        for right in tokens[i+1:]:
            X.append(abs(features[left]-features[right]));y.append(int(labels[left]==labels[right]))
    return np.vstack(X),np.array(y)


def _cross_session_pairs(path: Path) -> tuple[np.ndarray,np.ndarray]:
    truth={row["session"]:int(row["private_target"]) for row in csv.DictReader(
        (path/"private_session_ground_truth.csv").open(encoding="utf-8",newline=""))}
    features={}
    for session in truth:
        rows=jsonl(path/session/"server_visible_trace.jsonl")
        scheduled=np.array([int(row["scheduled_ns"]) for row in rows],dtype=np.float64)
        arrival=np.array([int(row["request_arrival_ns"]) for row in rows],dtype=np.float64)
        ready=np.array([int(row["answer_ready_ns"]) for row in rows],dtype=np.float64)
        features[session]=np.concatenate(((arrival-scheduled)/1e6,(ready-arrival)/1e6,np.diff(arrival)/1e6))
    X=[];y=[];sessions=sorted(features)
    for i,left in enumerate(sessions):
        for right in sessions[i+1:]:
            X.append(abs(features[left]-features[right]));y.append(int(truth[left]==truth[right]))
    return np.vstack(X),np.array(y)


def evaluate(root: Path, results: Path) -> dict[str,list[dict[str,object]]]:
    dev_single=results/"development_single";test_single=results/"confirmatory_final_single"
    dev_tool=results/"development_tool_sequences";test_tool=results/"confirmatory_final_tool_sequences"
    dev_pir=results/"development_pir";test_pir=results/"confirmatory_pir"
    action=[];tool=[];multi=[];pir=[];cross=[];holdout=[]

    Xd,yd,_=gateway_dataset(dev_single,"ACTION_TYPE");Xt,yt,_=gateway_dataset(test_single,"ACTION_TYPE")
    action=multiclass_holdout("ACTION_TYPE_TIMING",Xd,yd,Xt,yt)
    for row in action:row.update({"feature_set":"SOCKET_TIMING_ALL","split":"FROZEN_CONFIRMATORY"})
    for ablation in ("REQUEST_SLIP","REQUEST_INGRESS","RESPONSE_SLIP","RESPONSE_EGRESS","ROUND_TRIP",
                     "INTER_REQUEST","INTER_RESPONSE","SESSION_RELATIVE","ABSOLUTE_PHASE"):
        Xd,yd,_=gateway_dataset(dev_single,"ACTION_TYPE",ablation);Xt,yt,_=gateway_dataset(test_single,"ACTION_TYPE",ablation)
        for row in multiclass_holdout("ACTION_TYPE_ABLATION",Xd,yd,Xt,yt):
            row.update({"feature_set":ablation,"split":"FROZEN_CONFIRMATORY"});action.append(row)

    Xd,yd,_=gateway_dataset(dev_single,"TOOL_CLASS");Xt,yt,_=gateway_dataset(test_single,"TOOL_CLASS")
    for row in multiclass_holdout("TOOL_CLASS_TIMING",Xd,yd,Xt,yt):
        row.update({"feature_set":"SOCKET_TIMING_ALL","split":"FROZEN_CONFIRMATORY"});tool.append(row)
    for ablation in ("REQUEST_SLIP","REQUEST_INGRESS","RESPONSE_SLIP","RESPONSE_EGRESS","ROUND_TRIP",
                     "INTER_REQUEST","INTER_RESPONSE","SESSION_RELATIVE","ABSOLUTE_PHASE"):
        Xd,yd,_=gateway_dataset(dev_single,"TOOL_CLASS",ablation);Xt,yt,_=gateway_dataset(test_single,"TOOL_CLASS",ablation)
        for row in multiclass_holdout("TOOL_CLASS_ABLATION",Xd,yd,Xt,yt):
            row.update({"feature_set":ablation,"split":"FROZEN_CONFIRMATORY"});tool.append(row)
    pair_dev,y_pair_dev=_pair_gateway(dev_single,"TOOL_CLASS");pair_test,y_pair_test=_pair_gateway(test_single,"TOOL_CLASS")
    for row in binary_holdout("TOOL_REPEATED_TARGET_LINKABILITY",pair_dev,y_pair_dev,pair_test,y_pair_test):
        row.update({"feature_set":"SOCKET_TIMING_ALL","split":"FROZEN_CONFIRMATORY"});tool.append(row)

    Xd,yd,_=gateway_dataset(dev_tool,"TOOL_SEQUENCE");Xt,yt,_=gateway_dataset(test_tool,"TOOL_SEQUENCE")
    pairs={"TOOL_FREQUENCY_TSEQ0_V_TSEQ2":("TSEQ0","TSEQ2"),
           "TOOL_RARE_TSEQ0_V_TSEQ1":("TSEQ0","TSEQ1"),
           "TOOL_TRANSITION_TSEQ3_V_TSEQ4":("TSEQ3","TSEQ4")}
    for attack,(left,right) in pairs.items():
        dx,dy=select_binary(Xd,yd,left,right);tx,ty=select_binary(Xt,yt,left,right)
        for row in binary_holdout(attack,dx,dy,tx,ty):
            row.update({"feature_set":"SOCKET_TIMING_ALL","split":"FROZEN_CONFIRMATORY"});tool.append(row)

    profiles=("M0","M1","M2","M3","M4","M5","M6","M7","PIR_REAL_100","PIR_REAL_50","PIR_REAL_1")
    Xd,yd,_=pir_episode_dataset(dev_pir,profiles);Xt,yt,_=pir_episode_dataset(test_pir,profiles)
    pir_pairs={"AGENT_FREQUENCY_M0_V_M2":("M0","M2"),"RARE_AGENT_M0_V_M1":("M0","M1"),
               "HANDOFF_TRANSITION_M4_V_M5":("M4","M5"),"PIR_REAL_V_DUMMY_OCCUPANCY":("PIR_REAL_100","PIR_REAL_1")}
    for attack,(left,right) in pir_pairs.items():
        dx,dy=select_binary(Xd,yd,left,right);tx,ty=select_binary(Xt,yt,left,right)
        for row in binary_holdout(attack,dx,dy,tx,ty):
            row.update({"feature_set":"PIR_SERVER_TIMING","split":"FROZEN_CONFIRMATORY"});pir.append(row);multi.append(row.copy())
    pd,py=pir_query_pair_dataset(dev_pir,2000,71);pt,pty=pir_query_pair_dataset(test_pir,2000,72)
    for row in binary_holdout("PIR_REPEATED_TARGET_LINKABILITY",pd,py,pt,pty):
        row.update({"feature_set":"PIR_SERVER_TIMING","split":"FROZEN_CONFIRMATORY"});pir.append(row);multi.append(row.copy())
    for mode in ("REQUEST_SLIP","ANSWER_DURATION"):
        pd,py=pir_query_pair_dataset(dev_pir,2000,71,mode);pt,pty=pir_query_pair_dataset(test_pir,2000,72,mode)
        for row in binary_holdout("PIR_REPEATED_TARGET_ABLATION",pd,py,pt,pty):
            row.update({"feature_set":mode,"split":"FROZEN_CONFIRMATORY"});pir.append(row)

    cx,cy=_cross_session_pairs(results/"confirmatory_cross_session")
    cross=cross_validated_binary("CROSS_SESSION_TIMING_LINKABILITY",cx,cy)
    for row in cross:row.update({"feature_set":"PIR_SERVER_TIMING","split":"FROZEN_CONFIRMATORY_CV"})

    for collection in (action,tool,pir,multi,cross):holdout.extend(collection)
    write_csv(root/"ACTION_TIMING_RESULTS.csv",action)
    write_csv(root/"TOOL_TIMING_RESULTS.csv",tool)
    write_csv(root/"PIR_FIXED_SCHEDULE_RESULTS.csv",pir)
    write_csv(root/"MULTIROUND_TIMING_RESULTS.csv",multi)
    write_csv(root/"CROSS_SESSION_TIMING_RESULTS.csv",cross)
    write_csv(root/"TIMING_CONFIRMATORY_HOLDOUT_RESULTS.csv",holdout)
    overhead=aggregate_overhead(results);write_csv(root/"TIMING_OVERHEAD_RESULTS.csv",overhead)
    return {"action":action,"tool":tool,"pir":pir,"multi":multi,"cross":cross,"overhead":overhead}
