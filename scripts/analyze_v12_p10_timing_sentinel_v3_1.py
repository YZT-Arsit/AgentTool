from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analyze_v12_p10_timing_sentinel_resume as implementation  # noqa: E402

from v12_timing.classifier import MODEL_NAMES, sklearn_random_state  # noqa: E402
from v12_timing.sentinel_v3 import (  # noqa: E402
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.TARGET_TRAIN_COMPLETE_BLOCKS = TARGET_TRAIN_COMPLETE_BLOCKS
implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.completion_channel = completion_channel
implementation.select_complete_blocks = select_complete_blocks
implementation.validate_freeze_manifest = validate_freeze_manifest

BASE_CLOSED_DATASET_SHA = "d0536912a99907e0865c4ad2ecebfc73c5fa91ad"
METHODOLOGY_BASE_SHA = "63792088161deb6b1ccd3c4b4cb28babbf72f3ec"
ANALYSIS_SCHEMA = "AgentTool.V12P10TimingSentinelV31Analysis/1"
ANALYSIS_FILENAME = "sentinel_v3_1_analysis.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_seed_manifest(freeze: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for coordinate in freeze["physical_coordinates"]:
        for observer_index, observer in enumerate(coordinate["observers"]):
            raw = int(coordinate["analysis_seed"]) + observer_index
            folds = []
            for model_index, model in enumerate(MODEL_NAMES):
                for fold_index in range(5):
                    raw_fold = raw + 10_000 * (model_index + 1) + fold_index
                    folds.append(
                        {
                            "model": model,
                            "train_cv_fold": fold_index,
                            "raw_fold_seed64": raw_fold,
                            "sklearn_fold_seed32": sklearn_random_state(raw_fold),
                        }
                    )
            comparisons.append(
                {
                    "coordinate_id": coordinate["coordinate_id"],
                    "task": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "observer_index": observer_index,
                    "raw_coordinate_seed64": raw,
                    "sklearn_final_seed32": sklearn_random_state(raw),
                    "train_cv_folds": folds,
                }
            )
    return comparisons


def _expected_input_coordinates(
    freeze: dict[str, Any], selection: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    for coordinate in freeze["physical_coordinates"]:
        chosen = selection[coordinate["coordinate_id"]]
        rows.append(
            {
                "coordinate_id": coordinate["coordinate_id"],
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "observers": coordinate["observers"],
                "train_block_ids": chosen["SENTINEL_TRAIN"]["selected_planned_blocks"],
                "train_identity_ids": chosen["SENTINEL_TRAIN"]["selected_identities"],
                "eval_block_ids": chosen["SENTINEL_EVAL"]["selected_planned_blocks"],
                "eval_identity_ids": chosen["SENTINEL_EVAL"]["selected_identities"],
            }
        )
    return rows


def _git_preflight() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_CLOSED_DATASET_SHA, head],
        cwd=ROOT,
        check=True,
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{BASE_CLOSED_DATASET_SHA}..{head}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    protected_prefixes = (
        "common_action_gateway_v2/",
        "pir_integration/",
        "v11_online/",
        "v11_full_scope/",
    )
    protected_exact = {
        "v12_timing/pacer.py",
        "v12_timing/scheduler.py",
        "v12_timing/projection.py",
    }
    forbidden = [
        path
        for path in changed
        if path in protected_exact or path.startswith(protected_prefixes)
    ]
    if forbidden:
        raise RuntimeError(f"protected runtime diff is not NONE: {forbidden}")
    return head


def _paper_summary(output: Path, comparisons: list[dict[str, Any]]) -> None:
    compact = []
    worst: dict[str, dict[str, float]] = {}
    for row in comparisons:
        compact.append(
            {
                "task": row["task_id"],
                "framework": row["framework"],
                "observer": row["observer"],
                "selected_model": row["selected_train_model"],
                "train_cv_distinguishability_auc": row["train_distinguishability_auc"],
                "eval_auc": row["eval_point_auc"],
                "ci95_low": row["eval_ci95_two_sided_low"],
                "ci95_high": row["eval_ci95_two_sided_high"],
                "lcb99_5": row["eval_lcb99_5_one_sided"],
                "randomization_p": row["randomization"]["one_sided_randomization_p"],
                "early_timing_failure": row["early_fail"],
            }
        )
        task = str(row["task_id"])
        task_worst = worst.setdefault(
            task, {"worst_eval_auc": 0.0, "worst_lcb99_5": 0.0}
        )
        task_worst["worst_eval_auc"] = max(
            task_worst["worst_eval_auc"], float(row["eval_point_auc"])
        )
        task_worst["worst_lcb99_5"] = max(
            task_worst["worst_lcb99_5"], float(row["eval_lcb99_5_one_sided"])
        )
    implementation.write_json(
        output / "paper_planning_summary_v3_1.json",
        {
            "schema": "AgentTool.V12P10TimingSentinelV31PaperPlanning/1",
            "role": "DEVELOPMENT_SENTINEL_NOT_FINAL_PAPER_CONFIRMATORY_EVIDENCE",
            "comparisons": compact,
            "worst_by_task": worst,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the single frozen P10 V3.1 analysis."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed-manifest", type=Path, required=True)
    parser.add_argument("--analysis-input-manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite V3.1 analysis: {args.output}")
    head = _git_preflight()
    freeze = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(freeze)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    seeds = json.loads(args.seed_manifest.read_text(encoding="utf-8"))
    frozen_input = json.loads(args.analysis_input_manifest.read_text(encoding="utf-8"))
    if protocol["statistical_protocol"] != "V12_TIMING_STATISTICAL_PROTOCOL_V3_1":
        raise RuntimeError("wrong analysis protocol")
    for relative, expected in protocol["analysis_source_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"V3.1 analysis source hash mismatch: {relative}")
    if sha256(args.seed_manifest) != protocol["seed_domain_manifest_sha256"]:
        raise RuntimeError("seed-domain manifest hash mismatch")
    if (
        sha256(args.analysis_input_manifest)
        != protocol["analysis_input_manifest_sha256"]
    ):
        raise RuntimeError("analysis-input manifest hash mismatch")
    if seeds["comparisons"] != _expected_seed_manifest(freeze):
        raise RuntimeError("seed-domain mapping differs from frozen protocol seeds")
    if (
        seeds["invalid_sklearn_random_states"] != 0
        or seeds["unintended_duplicate_fold_seed_comparisons"]
    ):
        raise RuntimeError("seed-domain audit did not pass")
    records, dataset = implementation._verify_closed_dataset(args.input, freeze)
    if len(records) != 5040:
        raise RuntimeError("closed dataset identity count changed")
    if sum(row["status"] == "COMPLETE" for row in records) != 5025:
        raise RuntimeError("closed dataset COMPLETE count changed")
    if sum(row["status"] == "FAILED" for row in records) != 15:
        raise RuntimeError("closed dataset FAILED count changed")
    if (
        sha256(args.input / "dataset_manifest.json")
        != frozen_input["dataset_manifest_sha256"]
    ):
        raise RuntimeError("closed dataset manifest hash changed")
    status_by_identity = {str(row["identity"]): str(row["status"]) for row in records}
    completion = completion_channel(freeze, status_by_identity)
    selection = select_complete_blocks(freeze, status_by_identity)
    if selection != frozen_input["selection"]:
        raise RuntimeError("selected complete blocks changed after V3.1 freeze")
    if frozen_input["coordinates"] != _expected_input_coordinates(freeze, selection):
        raise RuntimeError("V3.1 analysis identity inventory changed")
    args.output.mkdir(parents=True)
    implementation.write_json(args.output / "completion_channel.json", completion)
    implementation.write_json(args.output / "selected_complete_blocks.json", selection)
    results = implementation._analysis_rows(records, freeze, selection)
    seed_by_comparison = {
        (row["task"], row["framework"], row["observer"]): row
        for row in seeds["comparisons"]
    }
    for row in results:
        seed = seed_by_comparison[(row["task_id"], row["framework"], row["observer"])]
        row["raw_protocol_seed64"] = seed["raw_coordinate_seed64"]
        row["sklearn_final_seed32"] = seed["sklearn_final_seed32"]
    verdict, timing_verdict, ready = implementation._combined_verdict(
        completion, selection, results
    )
    report = {
        "schema": ANALYSIS_SCHEMA,
        "statistical_protocol": "V12_TIMING_STATISTICAL_PROTOCOL_V3_1",
        "base_closed_dataset_evidence": BASE_CLOSED_DATASET_SHA,
        "methodology_base": METHODOLOGY_BASE_SHA,
        "analysis_source_commit": head,
        "root_cause": "ANALYSIS_RANDOM_STATE_DOMAIN_MISMATCH",
        "seed_conversion": "UINT64_MOD_2_POW_32",
        "invalid_sklearn_random_states": 0,
        "protected_runtime_diff": "NONE",
        "original_analysis_attempts": 1,
        "original_completed_classifier_fits": 0,
        "original_protected_auc_calculations": 0,
        "new_protected_sessions": 0,
        "closed_dataset_reused": True,
        "dataset_identity_count": 5040,
        "complete_sessions": 5025,
        "failed_sessions": 15,
        "failure_channel_flag": any(row["failure_channel_flag"] for row in completion),
        "operational_reliability_concern": any(
            row["operational_reliability_concern"] for row in completion
        ),
        "selected_train_blocks_per_physical_coordinate": 180,
        "selected_eval_blocks_per_physical_coordinate": 120,
        "observer_comparisons": results,
        "P10_sentinel_timing": timing_verdict,
        "P10_sentinel": verdict,
        "P10_full": "NOT_RUN",
        "P20_sentinel": "NOT_RUN",
        "P25_sentinel": "NOT_RUN",
        "selected_timing_delta_ms": "NONE",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "ready_for_P10_full_development": ready,
        "ready_for_timing_confirmatory": False,
        "ready_for_final_v12_holdout": False,
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "seed_domain_manifest_sha256": sha256(args.seed_manifest),
        "analysis_input_manifest_sha256": sha256(args.analysis_input_manifest),
        "platform_diagnostics": implementation._platform_diagnostics(records),
    }
    implementation.write_json(args.output / ANALYSIS_FILENAME, report)
    with (args.output / "observer_comparisons_v3_1.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = (
            "task_id",
            "framework",
            "observer",
            "raw_protocol_seed64",
            "sklearn_final_seed32",
            "selected_train_model",
            "train_cv_raw_auc",
            "train_score_orientation",
            "train_distinguishability_auc",
            "eval_point_auc",
            "eval_ci95_two_sided_low",
            "eval_ci95_two_sided_high",
            "eval_lcb99_5_one_sided",
            "early_fail",
            "train_blocks",
            "eval_blocks",
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    _paper_summary(args.output, results)
    print(
        json.dumps(
            {
                "P10_sentinel": verdict,
                "P10_sentinel_timing": timing_verdict,
                "ready_for_P10_full_development": ready,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
