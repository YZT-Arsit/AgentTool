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
from v12_timing.sentinel_smoke import (
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


def write_new(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite smoke analysis freeze: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def seed_manifest(freeze: dict[str, Any]) -> dict[str, Any]:
    comparisons = []
    duplicates = []
    for coordinate in freeze["physical_coordinates"]:
        for observer_index, observer in enumerate(coordinate["observers"]):
            raw = int(coordinate["analysis_seed"]) + observer_index
            folds = []
            normalized = []
            for model_index, model in enumerate(MODEL_NAMES):
                for fold_index in range(5):
                    raw_fold = raw + 10_000 * (model_index + 1) + fold_index
                    seed32 = sklearn_random_state(raw_fold)
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
                    "raw_coordinate_seed64": raw,
                    "sklearn_final_seed32": sklearn_random_state(raw),
                    "train_cv_folds": folds,
                }
            )
    if len(comparisons) != 7 or duplicates:
        raise RuntimeError("smoke seed-domain audit failed")
    return {
        "schema": "AgentTool.V12DuplexRepairSmokeSeedManifest/1",
        "conversion_rule": "UINT64_MOD_2_POW_32",
        "invalid_sklearn_random_states": 0,
        "unintended_duplicate_fold_seed_comparisons": duplicates,
        "comparisons": comparisons,
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
        not part["sufficient"] for row in selection.values() for part in row.values()
    ):
        raise RuntimeError(
            "smoke dataset lacks the predeclared complete-block denominator"
        )
    coordinates = []
    for coordinate in freeze["physical_coordinates"]:
        chosen = selection[coordinate["coordinate_id"]]
        coordinates.append(
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
    inputs = {
        "schema": "AgentTool.V12DuplexRepairSmokeAnalysisInput/1",
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "identity_count": TOTAL_SESSIONS,
        "selection": selection,
        "coordinates": coordinates,
    }
    seed_path = args.output_dir / "seed_domain_manifest.json"
    input_path = args.output_dir / "analysis_input_manifest.json"
    write_new(seed_path, seed_manifest(freeze))
    write_new(input_path, inputs)
    print(
        json.dumps(
            {
                "seed_manifest_sha256": sha256(seed_path),
                "analysis_input_manifest_sha256": sha256(input_path),
                "failure_channel_flags": sum(
                    bool(row["failure_channel_flag"]) for row in completion
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
