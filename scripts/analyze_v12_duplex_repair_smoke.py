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

import analyze_v12_p10_timing_sentinel_resume as implementation

from v12_timing.classifier import MODEL_NAMES, sklearn_random_state
from v12_timing.sentinel_smoke import (
    BOOTSTRAP_RESAMPLES,
    HISTORICAL_P10_RESULT_SHA,
    RANDOMIZATION_RESAMPLES,
    SMOKE_FAILURE_MARGIN,
    SMOKE_LCB_QUANTILE,
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
implementation.SENTINEL_BOOTSTRAP_RESAMPLES = BOOTSTRAP_RESAMPLES
implementation.SENTINEL_RANDOMIZATION_RESAMPLES = RANDOMIZATION_RESAMPLES
implementation.SENTINEL_LCB_QUANTILE = SMOKE_LCB_QUANTILE
implementation.SENTINEL_EARLY_FAIL_MARGIN = SMOKE_FAILURE_MARGIN

HISTORICAL_RELAY_AUCS = {
    ("T7", "OpenAI Agents SDK", "RELAY"): 0.980763888888889,
    (
        "T7",
        "Microsoft Agent Framework",
        "RELAY",
    ): 0.9693055555555555,
    ("T9", "OpenAI Agents SDK", "RELAY"): 0.9779861111111111,
    ("T9", "Microsoft Agent Framework", "RELAY"): 0.9902777777777778,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_seeds(freeze: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
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
            rows.append(
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
    return rows


def expected_inputs(
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed-manifest", type=Path, required=True)
    parser.add_argument("--analysis-input-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite smoke analysis: {args.output}")
    freeze = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(freeze)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != freeze["execution_source_commit"]:
        raise RuntimeError("smoke analysis commit differs from frozen execution source")
    for relative, expected in freeze["analysis_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"smoke analysis source hash mismatch: {relative}")
    seeds = json.loads(args.seed_manifest.read_text(encoding="utf-8"))
    frozen_input = json.loads(args.analysis_input_manifest.read_text(encoding="utf-8"))
    if seeds["comparisons"] != expected_seeds(freeze):
        raise RuntimeError("smoke seed mapping differs from frozen protocol")
    if (
        seeds["invalid_sklearn_random_states"]
        or seeds["unintended_duplicate_fold_seed_comparisons"]
    ):
        raise RuntimeError("smoke seed-domain audit failed")
    records, dataset = implementation._verify_closed_dataset(args.input, freeze)
    status = {str(row["identity"]): str(row["status"]) for row in records}
    completion = completion_channel(freeze, status)
    selection = select_complete_blocks(freeze, status)
    if selection != frozen_input["selection"] or frozen_input[
        "coordinates"
    ] != expected_inputs(freeze, selection):
        raise RuntimeError("smoke selected blocks changed after input freeze")
    args.output.mkdir(parents=True)
    implementation.write_json(args.output / "completion_channel.json", completion)
    implementation.write_json(args.output / "selected_complete_blocks.json", selection)
    results = implementation._analysis_rows(records, freeze, selection)
    seed_index = {
        (row["task"], row["framework"], row["observer"]): row
        for row in seeds["comparisons"]
    }
    for row in results:
        seed = seed_index[(row["task_id"], row["framework"], row["observer"])]
        row["raw_protocol_seed64"] = seed["raw_coordinate_seed64"]
        row["sklearn_final_seed32"] = seed["sklearn_final_seed32"]
        if row["status"] == "EVALUATED":
            row["eval_lcb95_one_sided"] = row.pop("eval_lcb99_5_one_sided")
            row["repair_smoke_failure"] = row.pop("early_fail")
            row["randomization_p"] = row["randomization"]["one_sided_randomization_p"]
    insufficient = any(row["status"] != "EVALUATED" for row in results)
    timing_failure = any(row.get("repair_smoke_failure", False) for row in results)
    failure_channel = any(row["failure_channel_flag"] for row in completion)
    operational = any(row["operational_reliability_concern"] for row in completion)
    if insufficient:
        verdict = "NOT_EVALUABLE_INSUFFICIENT_COMPLETE_BLOCKS"
        ready = False
    elif timing_failure:
        verdict = "FAIL_SUBSTANTIAL_RESIDUAL_DISTINGUISHABILITY"
        ready = False
    elif failure_channel or operational:
        verdict = "NOT_EVALUABLE"
        ready = False
    else:
        verdict = "PASS_TO_FULL_SENTINEL"
        ready = True
    ablation = []
    for row in results:
        key = (row["task_id"], row["framework"], row["observer"])
        if key in HISTORICAL_RELAY_AUCS and row["status"] == "EVALUATED":
            ablation.append(
                {
                    "task": key[0],
                    "framework": key[1],
                    "observer": key[2],
                    "historical_one_sided_P10_AUC": HISTORICAL_RELAY_AUCS[key],
                    "duplex_repair_smoke_AUC": row["eval_point_auc"],
                    "AUC_reduction": HISTORICAL_RELAY_AUCS[key]
                    - row["eval_point_auc"],
                    "datasets_combined": False,
                    "role": "DEVELOPMENT_ABLATION_ONLY",
                }
            )
    report = {
        "schema": "AgentTool.V12DuplexRepairSmokeAnalysis/1",
        "phase": "V12-DUPLEX-REPAIR-SMOKE-SENTINEL",
        "historical_result_commit": HISTORICAL_P10_RESULT_SHA,
        "execution_source_commit": head,
        "planned_sessions": TOTAL_SESSIONS,
        "executed_sessions": TOTAL_SESSIONS,
        "complete_sessions": sum(row["status"] == "COMPLETE" for row in records),
        "failed_sessions": sum(row["status"] == "FAILED" for row in records),
        "retries": 0,
        "completion_channel": completion,
        "observer_comparisons": results,
        "smoke_failure_rule": "ANY one-sided LCB95 > 0.65",
        "duplex_repair_smoke": verdict,
        "ready_for_full_duplex_sentinel": ready,
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "P10_full": "NOT_RUN",
        "P20": "NOT_RUN",
        "P25": "NOT_RUN",
        "confirmatory": "NOT_RUN",
        "final_holdout": "NOT_RUN",
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "seed_domain_manifest_sha256": sha256(args.seed_manifest),
        "analysis_input_manifest_sha256": sha256(args.analysis_input_manifest),
        "historical_one_sided_vs_duplex_smoke": ablation,
        "platform_diagnostics": implementation._platform_diagnostics(records),
    }
    implementation.write_json(args.output / "duplex_repair_smoke_analysis.json", report)
    with (args.output / "observer_comparisons.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = (
            "task_id",
            "framework",
            "observer",
            "selected_train_model",
            "train_distinguishability_auc",
            "eval_point_auc",
            "eval_ci95_two_sided_low",
            "eval_ci95_two_sided_high",
            "eval_lcb95_one_sided",
            "randomization_p",
            "repair_smoke_failure",
        )
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"duplex_repair_smoke": verdict, "ready": ready}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
