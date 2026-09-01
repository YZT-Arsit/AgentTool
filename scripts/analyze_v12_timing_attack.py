from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.attack import (
    conservative_best,
    evaluate_binary_attack_family,
    positive_control_informative,
    protected_pass,
    sentinel_early_fail,
)
from v12_timing.isolated_tasks import CLAIM_OBSERVERS, FRAMEWORKS, TASKS
from v12_timing.projection import timing_feature_vector


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(roots: Iterable[Path]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for root in roots:
        completion = json.loads((root / "campaign_completion.json").read_text(encoding="utf-8"))
        if completion["status"] != "PASS" or completion["completed_sessions"] != completion["expected_sessions"]:
            raise RuntimeError(f"incomplete timing campaign: {root}")
        paths = sorted((root / "sessions").glob("*/isolated_timing_record.json"))
        if len(paths) != int(completion["expected_sessions"]):
            raise RuntimeError(f"timing record denominator mismatch: {root}")
        values.extend(json.loads(path.read_text(encoding="utf-8")) for path in paths)
    return values


def quantile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


def distribution(values: list[int]) -> dict[str, int]:
    return {
        "count": len(values),
        "p50": quantile(values, 0.50),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
        "max": max(values, default=0),
    }


def evaluate(
    rows: list[dict[str, Any]],
    *,
    freeze: dict[str, Any],
    dataset: str,
    delta: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    widths = freeze["feature_raw_widths"][dataset][str(delta)]
    seed_base = int(str(freeze["model_seed_sha256"]), 16) % (2**31 - 1)
    for task_index, task_id in enumerate(TASKS):
        for framework_index, framework in enumerate(FRAMEWORKS):
            selected = [row for row in rows if row["task_id"] == task_id and row["framework"] == framework]
            if not selected:
                continue
            labels = [int(row["label"]) for row in selected]
            groups = [int(row["block"]) for row in selected]
            for observer_index, observer in enumerate(CLAIM_OBSERVERS[task_id]):
                vectors = [
                    timing_feature_vector(
                        row[f"{observer.lower()}_projection"],
                        raw_widths=widths[task_id][observer],
                    )
                    for row in selected
                ]
                models = evaluate_binary_attack_family(
                    vectors,
                    labels,
                    groups,
                    seed=seed_base + task_index * 1000 + framework_index * 100 + observer_index,
                    resamples=int(freeze["statistics"]["bootstrap_resamples"]),
                )
                best = conservative_best(models)
                results.append(
                    {
                        "task_id": task_id,
                        "task": TASKS[task_id],
                        "framework": framework,
                        "observer": observer,
                        "sessions": len(selected),
                        "sessions_per_class": len(selected) // 2,
                        "blocks": len(set(groups)),
                        "best": best.as_dict(),
                        "models": [value.as_dict() for value in models],
                        "positive_control_informative": positive_control_informative(best) if dataset == "CONTROL" else None,
                        "protected_pass": protected_pass(best) if dataset == "PROTECTED" else None,
                        "sentinel_early_fail": sentinel_early_fail(best) if dataset == "PROTECTED" else None,
                    }
                )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--protected-root", type=Path, action="append", default=[])
    parser.add_argument("--stage", choices=("CONTROL", "SENTINEL", "FULL"), required=True)
    parser.add_argument("--delta", type=int, choices=(10, 20, 25), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite timing analysis: {args.output}")
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    control_rows = records([args.control_root])
    control_results = evaluate(control_rows, freeze=freeze, dataset="CONTROL", delta=0)
    control_by_key = {
        (item["task_id"], item["framework"], item["observer"]): item
        for item in control_results
    }
    protected_rows: list[dict[str, Any]] = []
    protected_results: list[dict[str, Any]] = []
    if args.stage != "CONTROL":
        protected_rows = records(args.protected_root)
        protected_results = evaluate(protected_rows, freeze=freeze, dataset="PROTECTED", delta=args.delta)
        for item in protected_results:
            control = control_by_key[(item["task_id"], item["framework"], item["observer"])]
            item["positive_control"] = control["best"]
            item["positive_control_informative"] = control["positive_control_informative"]
            item["claim_eligible"] = bool(control["positive_control_informative"])
    informative_controls = [item for item in control_results if item["positive_control_informative"]]
    noninformative = [
        {key: item[key] for key in ("task_id", "framework", "observer")}
        for item in control_results
        if not item["positive_control_informative"]
    ]
    early_failures = [
        item
        for item in protected_results
        if item["claim_eligible"] and item["sentinel_early_fail"]
    ]
    protected_failures = [
        item
        for item in protected_results
        if item["claim_eligible"] and not item["protected_pass"]
    ]
    jitter = {}
    if protected_rows:
        jitter = {
            "nominal_late_cells_total": sum(int(row["nominal_late_cells"]) for row in protected_rows),
            "launch_slip_ns": distribution([int(value) for row in protected_rows for value in row["launch_slip_ns"]]),
            "request_gap_ns": distribution([int(value) for row in protected_rows for value in row["request_gap_ns"]]),
            "response_gap_ns": distribution([int(value) for row in protected_rows for value in row["response_gap_ns"]]),
            "session_span_ns": distribution([int(row["session_span_ns"]) for row in protected_rows]),
            "pir_query_gap_ns": distribution([int(value) for row in protected_rows for value in row["pir_query_gap_ns"]]),
            "pir_query_response_ns": distribution([int(value) for row in protected_rows for value in row["pir_query_response_ns"]]),
        }
    if args.stage == "CONTROL":
        status = "PASS" if informative_controls else "FAIL"
    elif args.stage == "SENTINEL":
        status = "EARLY_FAIL" if early_failures else "PASS_TO_FULL"
    else:
        status = "PASS" if not protected_failures else "FAIL"
    report = {
        "schema": "AgentTool.V12IsolatedTimingAttackAnalysis/1",
        "stage": args.stage,
        "delta_ms": args.delta,
        "freeze_sha256": sha(args.freeze),
        "control_sessions": len(control_rows),
        "protected_sessions": len(protected_rows),
        "control_results": control_results,
        "protected_results": protected_results,
        "control_non_informative": noninformative,
        "early_failure_keys": [
            {key: item[key] for key in ("task_id", "framework", "observer")}
            for item in early_failures
        ],
        "protected_failure_keys": [
            {key: item[key] for key in ("task_id", "framework", "observer")}
            for item in protected_failures
        ],
        "jitter": jitter,
        "status": status,
        "timing_confirmatory_sessions": 0,
    }
    args.output.mkdir(parents=True)
    (args.output / "attack_analysis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    with (args.output / "attack_analysis.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "dataset", "task_id", "framework", "observer", "sessions_per_class", "model",
                "auc", "ci_low", "ci_high", "informative", "protected_pass", "sentinel_early_fail",
            ),
        )
        writer.writeheader()
        for dataset, values in (("CONTROL", control_results), ("PROTECTED", protected_results)):
            for item in values:
                best = item["best"]
                writer.writerow(
                    {
                        "dataset": dataset,
                        "task_id": item["task_id"],
                        "framework": item["framework"],
                        "observer": item["observer"],
                        "sessions_per_class": item["sessions_per_class"],
                        "model": best["model"],
                        "auc": best["auc"],
                        "ci_low": best["ci_low"],
                        "ci_high": best["ci_high"],
                        "informative": item["positive_control_informative"],
                        "protected_pass": item.get("protected_pass"),
                        "sentinel_early_fail": item.get("sentinel_early_fail"),
                    }
                )
    return 0 if status in {"PASS", "PASS_TO_FULL"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
