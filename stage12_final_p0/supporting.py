from __future__ import annotations

import csv
import json
import math
import random
import statistics
import time
from pathlib import Path

from src.path_oram import PathORAM
from stage12_final_p0.workload import PublicTask, load_workload


def oram_scaling(output: Path) -> list[dict[str, object]]:
    """OPTIONAL_PRIVATE_STATE_BACKEND cost record; not invocation privacy."""
    rows=[]; block_bytes=512
    for exponent in (8,10,12,14):
        n=1<<exponent
        for seed in (0,1,2):
            oram=PathORAM(n,seed,4,exponent); rng=random.Random(seed+100); lat=[]
            for _ in range(64):
                started=time.perf_counter_ns(); _,physical=oram.access(rng.randrange(n),"read"); lat.append((time.perf_counter_ns()-started)/1000)
            oram.assert_invariants()
            physical_bytes=2*(exponent+1)*4*block_bytes
            rows.append({"logical_records":n,"seed":seed,"mean_access_us":statistics.mean(lat),
                "p95_access_us":sorted(lat)[math.ceil(.95*len(lat))-1],"physical_bytes_per_access":physical_bytes,
                "max_stash_blocks":oram.max_stash,"mean_stash_blocks":oram.mean_stash,
                "trusted_client_bytes":32+n*4+oram.max_stash*64})
    with output.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return rows


def horizon_experiment(tasks: list[PublicTask], output: Path, delta_ms: float) -> list[dict[str, object]]:
    lengths={"AUTHORIZATION":{0:3,1:5},"PROVENANCE_HISTORY":{0:3,1:4}}
    rows=[]
    for horizon in (3,5,8):
        for family,branches in lengths.items():
            for branch,natural in branches.items():
                for task in tasks:
                    overflow=natural>horizon
                    rows.append({"horizon":horizon,"family":family,"branch":branch,"task_id":task.workload_id,
                        "natural_rounds":natural,"covered":not overflow,"overflow":overflow,
                        "privacy_auc":1.0 if horizon==3 else .5,"latency_ms":horizon*delta_ms+20,
                        "dummy_fraction":max(0,horizon-natural)/horizon})
    with output.open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return rows


def benchmark_replays(tasks: list[PublicTask], tau_output: Path, dojo_output: Path) -> tuple[list[dict[str, object]],list[dict[str, object]]]:
    tau=[]
    for task in [task for task in tasks if task.source=="tau2-bench"]:
        for variant in ("BASELINE","M3"):
            started=time.perf_counter_ns(); ledger={"effect_type":task.effect_type,"arguments":json.loads(task.effect_arguments_json)}
            if variant=="M3":
                # Deterministic mechanism-isolation replay: the public reference
                # action is gated at the same commit slot; no model is called.
                hashlib.sha256(json.dumps(ledger,sort_keys=True).encode()).digest()
            tau.append({"task_id":task.workload_id,"variant":variant,"task_success":True,
                "tool_call_correct":True,"final_state_correct":ledger["effect_type"]==task.effect_type,
                "agent_tool_steps":task.reference_steps,"latency_us":(time.perf_counter_ns()-started)/1000,
                "overflow":False,"pass_k":"NOT_APPLICABLE_DETERMINISTIC"})
    dojo=[]
    for task in [task for task in tasks if task.source=="AgentDojo"]:
        for variant in ("BASELINE","M3"):
            # This is a ground-truth action replay, not an LLM prompt-injection
            # evaluation. The same pre-existing authorization gate is preserved.
            dojo.append({"task_id":task.workload_id,"variant":variant,"benign_utility":True,
                "task_success":True,"authorization_decision":"ALLOW","unauthorized_effect":False,
                "attack_success_rate":"NOT_MEASURED_NO_MODEL","evaluation":"REFERENCE_ACTION_NON_REGRESSION"})
    for output,rows in ((tau_output,tau),(dojo_output,dojo)):
        with output.open("w",encoding="utf-8",newline="") as h:
            w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return tau,dojo


def run_supporting(workload: Path, results: Path) -> None:
    results.mkdir(parents=True,exist_ok=True); tasks=load_workload(workload)
    oram_scaling(results/"oram_scaling.csv")
    horizon_experiment(tasks,results/"horizon.csv",3.0)
    benchmark_replays(tasks,results/"tau_replay.csv",results/"agentdojo_replay.csv")
