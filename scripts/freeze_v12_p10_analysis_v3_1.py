from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.classifier import MODEL_NAMES, sklearn_random_state  # noqa: E402

FREEZE_PATH = ROOT / "V12_P10_TIMING_SENTINEL_V3_FREEZE.json"
SELECTION_PATH = (
    ROOT / "V12_P10_TIMING_SENTINEL_V3_EVIDENCE" / "selected_complete_blocks.json"
)
AUDIT_PATH = ROOT / "V12_P10_TIMING_SENTINEL_V3_EVIDENCE" / "DATASET_CLOSURE_AUDIT.json"
FAILURE_PATH = (
    ROOT / "V12_P10_TIMING_SENTINEL_V3_EVIDENCE" / "ANALYSIS_HARNESS_FAILURE.json"
)
SEED_OUTPUT = ROOT / "V12_P10_V3_1_SEED_DOMAIN_MANIFEST.json"
INPUT_OUTPUT = ROOT / "V12_P10_V3_1_ANALYSIS_INPUT_MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def seed_manifest(freeze: dict[str, Any]) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    invalid = 0
    duplicate_comparisons: list[str] = []
    for coordinate in freeze["physical_coordinates"]:
        for observer_index, observer in enumerate(coordinate["observers"]):
            raw_coordinate = int(coordinate["analysis_seed"]) + observer_index
            rows: list[dict[str, Any]] = []
            normalized_fold_seeds: list[int] = []
            for model_index, model in enumerate(MODEL_NAMES):
                for fold_index in range(5):
                    raw_fold = raw_coordinate + 10_000 * (model_index + 1) + fold_index
                    normalized = sklearn_random_state(raw_fold)
                    invalid += not 0 <= normalized <= 2**32 - 1
                    normalized_fold_seeds.append(normalized)
                    rows.append(
                        {
                            "model": model,
                            "train_cv_fold": fold_index,
                            "raw_fold_seed64": raw_fold,
                            "sklearn_fold_seed32": normalized,
                        }
                    )
            if len(normalized_fold_seeds) != len(set(normalized_fold_seeds)):
                duplicate_comparisons.append(
                    f"{coordinate['coordinate_id']}|{observer}"
                )
            comparisons.append(
                {
                    "coordinate_id": coordinate["coordinate_id"],
                    "task": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "observer_index": observer_index,
                    "raw_coordinate_seed64": raw_coordinate,
                    "sklearn_final_seed32": sklearn_random_state(raw_coordinate),
                    "train_cv_folds": rows,
                }
            )
    if len(comparisons) != 10:
        raise RuntimeError("V3.1 seed freeze requires exactly ten observer comparisons")
    if invalid or duplicate_comparisons:
        raise RuntimeError("V3.1 seed-domain audit failed")
    return {
        "schema": "AgentTool.V12P10TimingAnalysisSeedDomainManifest/1",
        "statistical_protocol": "V12_TIMING_STATISTICAL_PROTOCOL_V3_1",
        "conversion_rule": "UINT64_MOD_2_POW_32",
        "sklearn_required_version": "1.9.0",
        "model_tie_break_order": list(MODEL_NAMES),
        "train_cv_fold_count": 5,
        "raw_fold_seed_derivation": "raw_coordinate_seed64 + 10000 * (model_index + 1) + fold_index",
        "invalid_sklearn_random_states": invalid,
        "unintended_duplicate_fold_seed_comparisons": duplicate_comparisons,
        "comparisons": comparisons,
    }


def input_manifest(
    freeze: dict[str, Any], selection: dict[str, Any], audit: dict[str, Any]
) -> dict[str, Any]:
    coordinates: list[dict[str, Any]] = []
    for coordinate in freeze["physical_coordinates"]:
        coordinate_id = coordinate["coordinate_id"]
        selected = selection[coordinate_id]
        train = selected["SENTINEL_TRAIN"]
        evaluation = selected["SENTINEL_EVAL"]
        if (
            len(train["selected_planned_blocks"]) != 180
            or len(train["selected_identities"]) != 360
        ):
            raise RuntimeError(f"invalid frozen TRAIN selection for {coordinate_id}")
        if (
            len(evaluation["selected_planned_blocks"]) != 120
            or len(evaluation["selected_identities"]) != 240
        ):
            raise RuntimeError(f"invalid frozen EVAL selection for {coordinate_id}")
        coordinates.append(
            {
                "coordinate_id": coordinate_id,
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "observers": coordinate["observers"],
                "train_block_ids": train["selected_planned_blocks"],
                "train_identity_ids": train["selected_identities"],
                "eval_block_ids": evaluation["selected_planned_blocks"],
                "eval_identity_ids": evaluation["selected_identities"],
            }
        )
    return {
        "schema": "AgentTool.V12P10TimingAnalysisInputManifest/1",
        "statistical_protocol": "V12_TIMING_STATISTICAL_PROTOCOL_V3_1",
        "closed_dataset_evidence_sha": "d0536912a99907e0865c4ad2ecebfc73c5fa91ad",
        "identity_count": 5040,
        "complete_sessions": 5025,
        "failed_sessions": 15,
        "dataset_manifest_sha256": audit["dataset_manifest_sha256"],
        "dataset_inventory_sha256": audit["dataset_inventory_sha256"],
        "execution_ledger_sha256": audit["execution_ledger_sha256"],
        "selection_source_sha256": sha256(SELECTION_PATH),
        "selection_rule": "ALREADY_FROZEN_PRIORITY_FIRST_COMPLETE_BLOCKS",
        "selected_train_blocks_per_physical_coordinate": 180,
        "selected_eval_blocks_per_physical_coordinate": 120,
        "coordinates": coordinates,
        "selection": selection,
    }


def main() -> int:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    failure = json.loads(FAILURE_PATH.read_text(encoding="utf-8"))
    if audit["status"] != "PASS" or audit["expected_sessions"] != 5040:
        raise RuntimeError("closed dataset audit is not the frozen passing audit")
    if (
        failure["classifier_training_runs_completed"] != 0
        or failure["auc_calculations"] != 0
    ):
        raise RuntimeError("original failed analysis exposed a protected result")
    write_json(SEED_OUTPUT, seed_manifest(freeze))
    write_json(INPUT_OUTPUT, input_manifest(freeze, selection, audit))
    print(
        json.dumps(
            {
                "seed_manifest_sha256": sha256(SEED_OUTPUT),
                "analysis_input_manifest_sha256": sha256(INPUT_OUTPUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
