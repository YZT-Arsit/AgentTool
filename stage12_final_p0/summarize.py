from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def _number(value):
    if isinstance(value, bool): return float(value)
    if str(value).lower() in {"true", "false"}: return float(str(value).lower()=="true")
    return float(value)


def _mean(rows, key): return statistics.mean(_number(row[key]) for row in rows) if rows else 0.0


def summarize(results: Path) -> dict[str, object]:
    attacks=list(csv.DictReader((results/"attack_results.csv").open(encoding="utf-8")))
    variant=[]
    for runtime in sorted({r["runtime"] for r in attacks}):
        for family in sorted({r["family"] for r in attacks}):
            for mediation in ("M0","M1","M2","M3"):
                for feature in ("STRUCTURAL","SIZE","TIMING","ALL"):
                    rows=[r for r in attacks if r["runtime"]==runtime and r["family"]==family and r["variant"]==mediation and r["feature_set"]==feature]
                    auc=[float(r["auc"]) for r in rows]; perm=[float(r["permutation_auc"]) for r in rows]
                    variant.append({"runtime":runtime,"family":family,"variant":mediation,"feature_set":feature,
                        "mean_auc":statistics.mean(auc),"std_auc":statistics.stdev(auc),
                        "mean_accuracy":_mean(rows,"accuracy"),"mean_permutation_auc":statistics.mean(perm),"chance":.5})
    with (results/"variant_summary.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(variant[0]));w.writeheader();w.writerows(variant)

    profiles=[json.loads((results/f"runtime{i}_profile.json").read_text(encoding="utf-8")) for i in (1,2)]
    cadence=[]; sizes=[]; approval=[]
    for profile in profiles:
        for row in profile["cadence_evaluation"]:
            cadence.append({"runtime":profile["runtime"],**row,
                            "throughput_eps":1000.0/float(row["latency_ms"])})
        for row in profile["size_evaluation"]: sizes.append({"runtime":profile["runtime"],**row})
        for row in profile["approval_window_evaluation"]: approval.append({"runtime":profile["runtime"],**row})
    for name,rows in (("cadence_results.csv",cadence),("size_mode_results.csv",sizes),("approval_epoch_results.csv",approval)):
        with (results/name).open("w",encoding="utf-8",newline="") as h:
            w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    horizon=list(csv.DictReader((results/"horizon.csv").open(encoding="utf-8")))
    horizon_summary=[]
    for value in (3,5,8):
        rows=[r for r in horizon if int(r["horizon"])==value]
        branch_rates={f'{r["family"]}:{r["branch"]}':None for r in rows}
        for key in list(branch_rates):
            family,branch=key.split(":"); x=[r for r in rows if r["family"]==family and r["branch"]==branch]
            branch_rates[key]=_mean(x,"overflow")
        horizon_summary.append({"horizon":value,"coverage":_mean(rows,"covered"),"overflow_rate":_mean(rows,"overflow"),
            "privacy_auc":_mean(rows,"privacy_auc"),"latency_ms":_mean(rows,"latency_ms"),
            "dummy_fraction":_mean(rows,"dummy_fraction"),"conditional_overflow_json":json.dumps(branch_rates,sort_keys=True)})
    with (results/"horizon_summary.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(horizon_summary[0]));w.writeheader();w.writerows(horizon_summary)

    m3=[r for r in variant if r["variant"]=="M3"]
    aggregate={f:_mean([r for r in m3 if r["feature_set"]==f],"mean_auc") for f in ("STRUCTURAL","SIZE","TIMING","ALL")}
    payload={"stage12_decision":"C — TIMING/SIZE LIVE DEFENSE FAILS","pir_status":"REMOVE",
        "m3_auc":aggregate,"profiles":profiles,"horizon":horizon_summary,
        "security_definition":"NOT SUPPORTED","maturity":"CONTROLLED PROTOTYPE",
        "workload_tasks":40,"state_families":2,"dummy_external_effects":0,
        "authorization_equivalence":True,"effect_equivalence":True}
    (results/"summary.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload
