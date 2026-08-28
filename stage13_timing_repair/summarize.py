from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path
from typing import Any

from stage12_final_p0.workload import load_workload
from stage13_timing_repair.analysis import (_load_jsonl, _load_truth, features,
                                            grouped_attack, within_task_attack)
from stage13_timing_repair.splits import frozen_split


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def load_development(results: Path, stem: str) -> list[dict[str, Any]]:
    truth = _load_truth(results / f"{stem}_development_truth.csv")
    private = {row["run_id"]: row for row in _load_jsonl(results / f"{stem}_development_private.jsonl")}
    rows = _load_jsonl(results / f"{stem}_development.jsonl")
    for row in rows:
        row["_truth"] = truth[row["run_id"]]
        row["_private"] = private[row["run_id"]]
    return rows


def load_final(results: Path, stem: str) -> list[dict[str, Any]]:
    truth = _load_truth(results / f"{stem}_truth.csv")
    private = {row["run_id"]: row for row in _load_jsonl(results / f"{stem}_private_instrumentation.jsonl")}
    rows = _load_jsonl(results / f"{stem}_final_host.jsonl")
    for row in rows:
        row["_truth"] = truth[row["run_id"]]
        row["_private"] = private[row["run_id"]]
    return rows


def run(results: Path, workload: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    tasks = load_workload(workload); assignment = frozen_split(tasks)
    split_rows = [{"task_id": task.workload_id, "source": task.source,
                   "split": assignment[task.workload_id]} for task in tasks]
    _write_csv(results / "frozen_task_split.csv", split_rows)

    cadence_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []
    slip_rows: list[dict[str, Any]] = []
    invariant: dict[str, Any] = {"forbidden_fields": [], "runtimes": {}}
    for stem, runtime in (("runtime1", "Microsoft Agent Framework"),
                          ("runtime2", "OpenAI Agents SDK")):
        development = load_development(results, stem)
        for cadence in ("P90", "P95", "P99", "P99+1MS"):
            rows = [row for row in development if row["cadence"] == cadence]
            for layer in ("RECEIVER_ARRIVAL", "ALL_OBSERVER"):
                for model in ("LogisticRegression", "RandomForest"):
                    metric = grouped_attack(rows, layer, model, seed=1313)
                    cadence_rows.append({"runtime": runtime, "cadence": cadence,
                                         "delta_ms": rows[0]["delta_ms"], "feature_set": layer,
                                         "model": model, **metric})
            private_by_id = {row["run_id"]: row["_private"] for row in rows}
            aggregate_rows.append({
                "runtime": runtime, "phase": "DEVELOPMENT", "cadence": cadence,
                "variant": "M3", "episodes": len(rows), "delta_ms": rows[0]["delta_ms"],
                "overflow_rate": statistics.mean(float(row["overflow"]) for row in rows),
                "deadline_miss_rate": statistics.mean(float(row["deadline_miss_rate"]) for row in rows),
                "mean_latency_ms": statistics.mean(float(row["latency_ms"]) for row in rows),
                "throughput_eps": 1000 / statistics.mean(float(row["latency_ms"]) for row in rows),
                "dummy_fraction": statistics.mean(1 - sum(private_by_id[row["run_id"]]["private_slot_occupancy"]) / 5 for row in rows),
                "idle_fraction": statistics.mean(max(0.0, 1 - sum((e["t1"]-e["t0"])/1e6 for e in private_by_id[row["run_id"]]["private_instrumentation"]) / (5*float(row["delta_ms"]))) for row in rows),
            })
        final = load_final(results, stem)
        for variant in ("M2", "M3"):
            rows = [row for row in final if row["variant"] == variant]
            aggregate_rows.append({
                "runtime": runtime, "phase": "FINAL_TEST", "cadence": rows[0]["cadence"],
                "variant": variant, "episodes": len(rows), "delta_ms": rows[0]["delta_ms"],
                "overflow_rate": statistics.mean(float(row["overflow"]) for row in rows),
                "deadline_miss_rate": statistics.mean(float(row["deadline_miss_rate"]) for row in rows),
                "mean_latency_ms": statistics.mean(float(row["latency_ms"]) for row in rows),
                "throughput_eps": 1000 / statistics.mean(float(row["latency_ms"]) for row in rows),
                "dummy_fraction": statistics.mean(1 - sum(row["_private"]["private_slot_occupancy"]) / 5 for row in rows),
                "idle_fraction": statistics.mean(max(0.0, 1 - sum((e["t1"]-e["t0"])/1e6 for e in row["_private"]["private_instrumentation"]) / max(float(row["latency_ms"]), .001)) for row in rows),
            })
        m3 = [row for row in final if row["variant"] == "M3"]
        for family in ("AUTHORIZATION", "PROVENANCE_HISTORY"):
            for branch in (0, 1):
                rows = [row for row in m3 if row["_truth"]["family"] == family and int(row["_truth"]["branch"]) == branch]
                values = [event["release_slip_us"] for row in rows for event in row["host_visible_trace"]]
                ordered = sorted(values)
                pick = lambda q: ordered[min(len(ordered)-1, int(q*(len(ordered)-1)))]
                slip_rows.append({"runtime": runtime, "family": family, "branch": branch,
                                  "slots": len(values), "mean_us": statistics.mean(values),
                                  "p95_us": pick(.95), "p99_us": pick(.99), "max_us": max(values)})
        serialized = "\n".join(json.dumps(row["host_visible_trace"], sort_keys=True) for row in final)
        forbidden = [name for name in ("branch", "family", "private_state", "is_dummy", "real_internal") if name in serialized]
        invariant["forbidden_fields"].extend(forbidden)
        invariant["runtimes"][runtime] = {
            "episodes": len(final),
            "all_success": all(row["success"] for row in final),
            "authorization_preserved": all(row["_private"]["authorization_preserved"] for row in final),
            "effect_equivalent": all(row["_private"]["effect_equivalent"] for row in final),
            "effect_count_one": all(row["effect_count"] == 1 for row in final),
            "dummy_external_effects": sum(row["dummy_external_effects"] for row in final),
            "m3_fixed_count": all(len(row["host_visible_trace"]) == 5 for row in m3),
            "m3_fixed_size": all(event["receiver_bytes"] == 16384 for row in m3 for event in row["host_visible_trace"]),
            "m3_fixed_sequence": all([event["slot"] for event in row["host_visible_trace"]] == [1,2,3,4,5] for row in m3),
            "m3_oram_accesses": sorted({sum(event["oram_access_count"] for event in row["host_visible_trace"]) for row in m3}),
        }
    _write_csv(results / "cadence_attack.csv", cadence_rows)
    _write_csv(results / "operational_metrics.csv", aggregate_rows)
    _write_csv(results / "deadline_slip.csv", slip_rows)
    (results / "invariants.json").write_text(json.dumps(invariant, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run(Path("results_stage13"), Path("PUBLIC_DERIVED_WORKLOAD.csv"))
