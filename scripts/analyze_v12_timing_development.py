from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.attack import (
    conservative_best,
    evaluate_binary_attack_family,
    positive_control_informative,
    protected_pass,
)
from v12_timing.matrix import TASKS
from v12_timing.projection import timing_feature_vector


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(root: Path) -> list[dict[str, Any]]:
    paths = sorted((root / "sessions").glob("*/timing_record.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite timing analysis: {args.output}")
    args.output.mkdir(parents=True)
    completion = json.loads((args.input / "campaign_completion.json").read_text(encoding="utf-8"))
    rows = _records(args.input)
    if len(rows) != int(completion["expected_sessions"]):
        raise RuntimeError("timing campaign is incomplete")
    results: list[dict[str, Any]] = []
    for task_index, task in enumerate(TASKS):
        labels = [int(row["secret_labels"][task]) for row in rows]
        groups = [int(row["block"]) for row in rows]
        for observer in ("RELAY", "REGISTRY"):
            protected_vectors = [timing_feature_vector(row[f"{observer.lower()}_projection"]) for row in rows]
            protected_models = evaluate_binary_attack_family(
                protected_vectors, labels, groups, seed=args.seed + task_index * 100 + (0 if observer == "RELAY" else 1)
            )
            protected_best = conservative_best(protected_models)
            control_vectors = [timing_feature_vector(row["positive_controls"][task][observer]) for row in rows]
            control_models = evaluate_binary_attack_family(
                control_vectors, labels, groups, seed=args.seed + 50_000 + task_index * 100 + (0 if observer == "RELAY" else 1)
            )
            control_best = conservative_best(control_models)
            results.append(
                {
                    "task_id": task,
                    "task": TASKS[task],
                    "observer": observer,
                    "protected_best": protected_best.as_dict(),
                    "protected_models": [value.as_dict() for value in protected_models],
                    "protected_pass": protected_pass(protected_best),
                    "positive_control_best": control_best.as_dict(),
                    "positive_control_models": [value.as_dict() for value in control_models],
                    "positive_control_informative": positive_control_informative(control_best),
                }
            )
    functional = all(bool(row["functional"]) for row in rows)
    lateness = [int(row["lateness"]["nominal_late_cells"]) for row in rows]
    maximum_slips = [int(row["lateness"]["maximum_launch_slip_ns"]) for row in rows]
    report = {
        "schema": "AgentTool.V12TimingDevelopmentAttackResult/1",
        "source_campaign": str(args.input),
        "campaign_completion_sha256": _sha(args.input / "campaign_completion.json"),
        "sessions": len(rows),
        "sessions_per_class_per_task": len(rows) // 2,
        "functional_full_transcript_pass": functional,
        "all_positive_controls_informative": all(item["positive_control_informative"] for item in results),
        "all_protected_tasks_pass": all(item["protected_pass"] for item in results),
        "development_profile_pass": functional and all(item["positive_control_informative"] and item["protected_pass"] for item in results),
        "nominal_late_cells_total": sum(lateness),
        "nominal_late_cells_max_per_session": max(lateness),
        "maximum_launch_slip_ns": max(maximum_slips),
        "results": results,
    }
    json_path = args.output / "development_attack_results.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (args.output / "development_attack_results.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id", "task", "observer", "protected_model", "protected_auc",
                "protected_ci_low", "protected_ci_high", "protected_pass",
                "control_model", "control_auc", "control_ci_low", "control_ci_high",
                "control_informative",
            ],
        )
        writer.writeheader()
        for item in results:
            protected = item["protected_best"]
            control = item["positive_control_best"]
            writer.writerow(
                {
                    "task_id": item["task_id"], "task": item["task"], "observer": item["observer"],
                    "protected_model": protected["model"], "protected_auc": protected["auc"],
                    "protected_ci_low": protected["ci_low"], "protected_ci_high": protected["ci_high"],
                    "protected_pass": item["protected_pass"], "control_model": control["model"],
                    "control_auc": control["auc"], "control_ci_low": control["ci_low"],
                    "control_ci_high": control["ci_high"], "control_informative": item["positive_control_informative"],
                }
            )
    return 0 if report["development_profile_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
