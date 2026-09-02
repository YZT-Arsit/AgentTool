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
from v12_timing.sentinel_duplex import (
    BASE_DUPLEX_EVIDENCE,
    HISTORICAL_P10_RESULT_SHA,
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_seeds(freeze: dict[str, Any]) -> list[dict[str, Any]]:
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


def _expected_inputs(
    freeze: dict[str, Any], selection: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "coordinate_id": coordinate["coordinate_id"],
            "task": coordinate["task_id"],
            "framework": coordinate["framework"],
            "observers": coordinate["observers"],
            "train_block_ids": selection[coordinate["coordinate_id"]]["SENTINEL_TRAIN"][
                "selected_planned_blocks"
            ],
            "train_identity_ids": selection[coordinate["coordinate_id"]][
                "SENTINEL_TRAIN"
            ]["selected_identities"],
            "eval_block_ids": selection[coordinate["coordinate_id"]]["SENTINEL_EVAL"][
                "selected_planned_blocks"
            ],
            "eval_identity_ids": selection[coordinate["coordinate_id"]][
                "SENTINEL_EVAL"
            ]["selected_identities"],
        }
        for coordinate in freeze["physical_coordinates"]
    ]


def _historical_ablation(results: list[dict[str, Any]]) -> dict[str, Any]:
    historical_path = (
        ROOT / "V12_P10_TIMING_ANALYSIS_V3_1_EVIDENCE" / "sentinel_v3_1_analysis.json"
    )
    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    old = {
        (row["task_id"], row["framework"], row["observer"]): row
        for row in historical["observer_comparisons"]
    }
    rows = []
    for row in results:
        if (
            row["task_id"]
            not in {"T7_TOOL_VERSUS_AGENT_AS_TOOL", "T9_PROVIDER_READINESS"}
            or row["observer"] != "RELAY"
        ):
            continue
        prior = old[(row["task_id"], row["framework"], row["observer"])]
        rows.append(
            {
                "task": row["task_id"],
                "framework": row["framework"],
                "observer": row["observer"],
                "historical_one_sided_eval_auc": prior["eval_point_auc"],
                "historical_one_sided_lcb99_5": prior["eval_lcb99_5_one_sided"],
                "duplex_eval_auc": row["eval_point_auc"],
                "duplex_lcb99_5": row["eval_lcb99_5_one_sided"],
                "role": "DEVELOPMENT_ABLATION_NOT_CONFIRMATORY_EVIDENCE",
            }
        )
    return {
        "historical_result_commit": HISTORICAL_P10_RESULT_SHA,
        "interpretation": "DEVELOPMENT_ABLATION_ONLY",
        "comparisons": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the single frozen duplex P10 sentinel analysis."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed-manifest", type=Path, required=True)
    parser.add_argument("--analysis-input-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite duplex analysis: {args.output}")
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
        raise RuntimeError(
            "analysis repository commit differs from frozen execution source"
        )
    for relative, expected in freeze["analysis_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"frozen analysis source hash mismatch: {relative}")
    seeds = json.loads(args.seed_manifest.read_text(encoding="utf-8"))
    frozen_input = json.loads(args.analysis_input_manifest.read_text(encoding="utf-8"))
    if seeds["comparisons"] != _expected_seeds(freeze):
        raise RuntimeError("seed-domain manifest differs from frozen seeds")
    if (
        seeds["invalid_sklearn_random_states"]
        or seeds["unintended_duplicate_fold_seed_comparisons"]
    ):
        raise RuntimeError("seed-domain audit failed")
    records, dataset = implementation._verify_closed_dataset(args.input, freeze)
    status = {str(row["identity"]): str(row["status"]) for row in records}
    completion = completion_channel(freeze, status)
    selection = select_complete_blocks(freeze, status)
    if selection != frozen_input["selection"] or frozen_input[
        "coordinates"
    ] != _expected_inputs(freeze, selection):
        raise RuntimeError("analysis input blocks differ from pre-analysis freeze")
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
    verdict, timing_verdict, ready = implementation._combined_verdict(
        completion, selection, results
    )
    report = {
        "schema": "AgentTool.V12DuplexP10SentinelAnalysis/1",
        "protocol": "V3.1_DUPLEX_FEATURE_CONTRACT",
        "base_duplex_evidence": BASE_DUPLEX_EVIDENCE,
        "historical_one_sided_result": HISTORICAL_P10_RESULT_SHA,
        "execution_source_commit": head,
        "protected_runtime_diff": "NONE",
        "planned_identities": TOTAL_SESSIONS,
        "executed_identities": TOTAL_SESSIONS,
        "complete_sessions": sum(row["status"] == "COMPLETE" for row in records),
        "failed_sessions": sum(row["status"] == "FAILED" for row in records),
        "retries": 0,
        "completion_channel": completion,
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
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "seed_domain_manifest_sha256": sha256(args.seed_manifest),
        "analysis_input_manifest_sha256": sha256(args.analysis_input_manifest),
        "platform_diagnostics": implementation._platform_diagnostics(records),
        "historical_one_sided_vs_duplex_ablation": _historical_ablation(results),
    }
    implementation.write_json(args.output / "duplex_p10_sentinel_analysis.json", report)
    with (args.output / "observer_comparisons.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = (
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
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    implementation.write_json(
        args.output / "historical_one_sided_vs_duplex_ablation.json",
        report["historical_one_sided_vs_duplex_ablation"],
    )
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
