from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import analyze_v12_p10_timing_sentinel_resume as implementation

from v12_timing.classifier import MODEL_NAMES, sklearn_random_state
from v12_timing.sentinel_duplex import (
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite frozen analysis artifact: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def seed_manifest(freeze: dict[str, Any]) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    invalid = 0
    duplicates: list[str] = []
    for coordinate in freeze["physical_coordinates"]:
        for observer_index, observer in enumerate(coordinate["observers"]):
            raw_coordinate = int(coordinate["analysis_seed"]) + observer_index
            folds: list[dict[str, Any]] = []
            normalized: list[int] = []
            for model_index, model in enumerate(MODEL_NAMES):
                for fold_index in range(5):
                    raw_fold = raw_coordinate + 10_000 * (model_index + 1) + fold_index
                    seed32 = sklearn_random_state(raw_fold)
                    invalid += int(not 0 <= seed32 <= 2**32 - 1)
                    normalized.append(seed32)
                    folds.append(
                        {
                            "model": model,
                            "train_cv_fold": fold_index,
                            "raw_fold_seed64": raw_fold,
                            "sklearn_fold_seed32": seed32,
                        }
                    )
            if len(normalized) != len(set(normalized)):
                duplicates.append(f"{coordinate['coordinate_id']}|{observer}")
            comparisons.append(
                {
                    "coordinate_id": coordinate["coordinate_id"],
                    "task": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "observer_index": observer_index,
                    "raw_coordinate_seed64": raw_coordinate,
                    "sklearn_final_seed32": sklearn_random_state(raw_coordinate),
                    "train_cv_folds": folds,
                }
            )
    if len(comparisons) != 10 or invalid or duplicates:
        raise RuntimeError("duplex seed-domain audit failed")
    return {
        "schema": "AgentTool.V12DuplexP10SeedDomainManifest/1",
        "protocol": "V3.1_DUPLEX_FEATURE_CONTRACT",
        "conversion_rule": "UINT64_MOD_2_POW_32",
        "model_tie_break_order": list(MODEL_NAMES),
        "train_cv_fold_count": 5,
        "invalid_sklearn_random_states": invalid,
        "unintended_duplicate_fold_seed_comparisons": duplicates,
        "comparisons": comparisons,
    }


def input_manifest(
    freeze: dict[str, Any],
    selection: dict[str, Any],
    dataset: dict[str, Any],
    campaign_root: Path,
) -> dict[str, Any]:
    coordinates = []
    for coordinate in freeze["physical_coordinates"]:
        chosen = selection[coordinate["coordinate_id"]]
        train = chosen["SENTINEL_TRAIN"]
        evaluation = chosen["SENTINEL_EVAL"]
        if (
            len(train["selected_planned_blocks"]) != 180
            or len(train["selected_identities"]) != 360
        ):
            raise RuntimeError("duplex TRAIN input denominator failed")
        if (
            len(evaluation["selected_planned_blocks"]) != 120
            or len(evaluation["selected_identities"]) != 240
        ):
            raise RuntimeError("duplex EVAL input denominator failed")
        coordinates.append(
            {
                "coordinate_id": coordinate["coordinate_id"],
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
        "schema": "AgentTool.V12DuplexP10AnalysisInputManifest/1",
        "protocol": "V3.1_DUPLEX_FEATURE_CONTRACT",
        "identity_count": TOTAL_SESSIONS,
        "dataset_manifest_sha256": sha256(campaign_root / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "selection_rule": "FIRST_COMPLETE_BY_FROZEN_PARTITION_PRIORITY",
        "selected_train_blocks_per_physical_coordinate": 180,
        "selected_eval_blocks_per_physical_coordinate": 120,
        "coordinates": coordinates,
        "selection": selection,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    freeze = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(freeze)
    records, dataset = implementation._verify_closed_dataset(args.input, freeze)
    status = {str(row["identity"]): str(row["status"]) for row in records}
    completion = completion_channel(freeze, status)
    selection = select_complete_blocks(freeze, status)
    if any(
        not part["sufficient"]
        for coordinate in selection.values()
        for part in coordinate.values()
    ):
        raise RuntimeError(
            "insufficient complete blocks; decisive timing analysis is not evaluable"
        )
    seed_path = args.output_dir / "seed_domain_manifest.json"
    input_path = args.output_dir / "analysis_input_manifest.json"
    write_json(seed_path, seed_manifest(freeze))
    write_json(input_path, input_manifest(freeze, selection, dataset, args.input))
    print(
        json.dumps(
            {
                "seed_domain_manifest_sha256": sha256(seed_path),
                "analysis_input_manifest_sha256": sha256(input_path),
                "completion_channel_flags": sum(
                    bool(row["failure_channel_flag"]) for row in completion
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
