from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from stage12_final_p0.workload import PublicTask, load_workload
from stage13_timing_repair.egress import PersistentEgressShaper
from stage13_timing_repair.splits import frozen_split


EpisodeFn = Callable[[PublicTask,str,int,str,float,int,int,PersistentEgressShaper],Awaitable[dict[str,Any]]]


def percentile(values: list[float], p: float) -> float:
    ordered=sorted(values); return ordered[min(len(ordered)-1,max(0,math.ceil(p*len(ordered))-1))]


async def run_runtime(runtime: str, episode: EpisodeFn, workload_path: Path, results_dir: Path) -> None:
    tasks=load_workload(workload_path); splits=frozen_split(tasks)
    calibration=[task for task in tasks if splits[task.workload_id]=="CALIBRATION"]
    development=[task for task in tasks if splits[task.workload_id]=="DEVELOPMENT"]
    final=[task for task in tasks if splits[task.workload_id]=="FINAL_TEST"]
    stem="runtime1" if runtime.startswith("Microsoft") else "runtime2"
    frame_bytes=16384; horizon=5
    private_keys=("private_instrumentation","private_slot_occupancy","proposal_queue_time_ns",
                  "done_time_ns","worker_done_by_epoch_end","authorization_preserved",
                  "effect_equivalent","state_preserved")

    def separate_private(row: dict[str,Any], run_id: str) -> dict[str,Any]:
        private_row={"run_id":run_id}
        for key in private_keys:
            if key in row: private_row[key]=row.pop(key)
        return private_row
    work_ms=[]; calibration_rows=[]
    with PersistentEgressShaper() as shaper:
        calibration_specs=[(task,family,branch) for task in calibration
            for family in ("AUTHORIZATION","PROVENANCE_HISTORY") for branch in (0,1)]
        random.Random(13001).shuffle(calibration_specs)
        for order,(task,family,branch) in enumerate(calibration_specs):
            row=await episode(task,family,branch,"M2",1.0,frame_bytes,100000+order,shaper)
            calibration_rows.append({"task_id":task.workload_id,"family":family,"branch":branch,
                                     "latency_ms":row["latency_ms"],"overflow":row["overflow"]})
            work_ms.extend((event["t1"]-event["t0"])/1e6 for event in row["private_instrumentation"])
        deltas={"P90":percentile(work_ms,.90),"P95":percentile(work_ms,.95),"P99":percentile(work_ms,.99)}
        deltas["P99+1MS"]=deltas["P99"]+1.0
        dev_rows=[]; dev_truth=[]; dev_private=[]
        dev_specs=[(cadence,delta,task,family,branch,repetition) for cadence,delta in deltas.items()
            for task in development for family in ("AUTHORIZATION","PROVENANCE_HISTORY")
            for branch in (0,1) for repetition in range(2)]
        random.Random(13002).shuffle(dev_specs)
        for order,(cadence,delta,task,family,branch,repetition) in enumerate(dev_specs):
            run_id=f"{stem}-dev-{order}"
            row=await episode(task,family,branch,"M3",delta,frame_bytes,200000+order,shaper)
            dev_private.append(separate_private(row,run_id))
            row.update({"phase":"DEVELOPMENT","cadence":cadence,"delta_ms":delta,
                        "task_id":task.workload_id,"run_id":run_id,
                        "repetition":repetition,"variant":"M3","runtime":runtime})
            row.pop("family",None); row.pop("branch",None)
            dev_rows.append(row)
            dev_truth.append({"run_id":run_id,"task_id":task.workload_id,"family":family,
                              "branch":branch,"variant":"M3","runtime":runtime,"cadence":cadence})
        candidates=[]
        for cadence,delta in deltas.items():
            rows=[row for row in dev_rows if row["cadence"]==cadence]
            candidates.append({"cadence":cadence,"delta_ms":delta,
                "overflow_rate":statistics.mean(float(row["overflow"]) for row in rows),
                "deadline_miss_rate":statistics.mean(float(row["deadline_miss_rate"]) for row in rows),
                "mean_latency_ms":statistics.mean(float(row["latency_ms"]) for row in rows)})
        # Predeclared conservative final configuration. Development labels are
        # not consulted; the +1 ms safety margin is fixed before final testing.
        selected=next(row for row in candidates if row["cadence"]=="P99+1MS")
        final_rows=[]; truth=[]; private=[]
        final_specs=[(index,task,family,branch,repetition,mode) for index,task in enumerate(final)
            for family in ("AUTHORIZATION","PROVENANCE_HISTORY") for branch in (0,1)
            for repetition in range(3) for mode in ("M2","M3")]
        random.Random(13003).shuffle(final_specs)
        for order,(index,task,family,branch,repetition,mode) in enumerate(final_specs):
            delta=float(selected["delta_ms"]);run_id=f"{stem}-final-{order:04d}"
            row=await episode(task,family,branch,mode,delta,frame_bytes,300000+order,shaper)
            private.append(separate_private(row,run_id))
            row.update({"run_id":run_id,"phase":"FINAL_TEST","cadence":selected["cadence"],
                "delta_ms":delta,"task_id":task.workload_id,"repetition":repetition,
                "variant":mode,"runtime":runtime})
            row.pop("family",None); row.pop("branch",None);final_rows.append(row)
            truth.append({"run_id":run_id,"task_id":task.workload_id,"family":family,
                          "branch":branch,"variant":mode,"runtime":runtime})
    results_dir.mkdir(parents=True,exist_ok=True)
    def jsonl(path: Path, rows: list[dict[str,Any]]) -> None:
        with path.open("w",encoding="utf-8") as handle:
            for row in rows: handle.write(json.dumps(row,sort_keys=True)+"\n")
    jsonl(results_dir/f"{stem}_development.jsonl",dev_rows)
    jsonl(results_dir/f"{stem}_development_private.jsonl",dev_private)
    jsonl(results_dir/f"{stem}_final_host.jsonl",final_rows)
    jsonl(results_dir/f"{stem}_private_instrumentation.jsonl",private)
    with (results_dir/f"{stem}_truth.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(truth[0]));writer.writeheader();writer.writerows(truth)
    with (results_dir/f"{stem}_development_truth.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(dev_truth[0]));writer.writeheader();writer.writerows(dev_truth)
    (results_dir/f"{stem}_calibration.json").write_text(json.dumps({"runtime":runtime,"samples":len(work_ms),
        "work_ms_mean":statistics.mean(work_ms),"deltas_ms":deltas,"cadence_candidates":candidates,
        "selected":selected,"frame_bytes":frame_bytes,"horizon":horizon,
        "split_counts":{"calibration":len(calibration),"development":len(development),"final_test":len(final)},
        "test_labels_used_for_selection":False},indent=2),encoding="utf-8")
