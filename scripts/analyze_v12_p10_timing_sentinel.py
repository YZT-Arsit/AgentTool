from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.classifier import select_on_train_fit_predict_eval
from v12_timing.projection import timing_feature_vector
from v12_timing.sentinel import (
    SENTINEL_BOOTSTRAP_RESAMPLES,
    SENTINEL_EARLY_FAIL_MARGIN,
    SENTINEL_LCB_QUANTILE,
    SENTINEL_RANDOMIZATION_RESAMPLES,
    validate_freeze_manifest,
)
from v12_timing.statistics import (
    BlockSplit,
    matched_block_bootstrap_auc_values,
    paired_auc_randomization_test,
    selected_model_eval_auc,
    validate_matched_blocks,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def quantile(values: Iterable[int], probability: float) -> int:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        return 0
    return ordered[min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))]


def distribution(values: Iterable[int]) -> dict[str, int]:
    rows = list(values)
    return {
        "count": len(rows),
        "p50": quantile(rows, 0.50),
        "p95": quantile(rows, 0.95),
        "p99": quantile(rows, 0.99),
        "max": max(rows, default=0),
    }


def _verify_closed_dataset(campaign_root: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    completion = json.loads((campaign_root / "campaign_completion.json").read_text(encoding="utf-8"))
    dataset = json.loads((campaign_root / "dataset_manifest.json").read_text(encoding="utf-8"))
    if completion.get("status") != "COLLECTION_CLOSED_COMPLETE":
        raise RuntimeError("sentinel analysis requires a closed complete collection")
    if int(completion.get("completed_sessions", -1)) != 4800 or int(completion.get("retries", -1)) != 0:
        raise RuntimeError("sentinel collection denominator/retry contract failed")
    if dataset.get("collection_closed") is not True or int(dataset.get("session_record_count", -1)) != 4800:
        raise RuntimeError("sentinel dataset manifest is incomplete")
    if dataset.get("frozen_manifest_sha256") != sha256(campaign_root / "frozen_manifest.json"):
        raise RuntimeError("sentinel frozen manifest hash drifted after collection")
    records: list[dict[str, Any]] = []
    for row in dataset["session_records"]:
        path = campaign_root / row["path"]
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"sentinel timing record hash mismatch: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("functional_integrity_pass") is not True:
            raise RuntimeError("sentinel dataset contains a failed session")
        records.append(record)
    if {row["identity"] for row in records} != set(manifest["identity_manifest"]):
        raise RuntimeError("sentinel closed dataset identity inventory drifted")
    return records


def _analysis_rows(
    records: list[dict[str, Any]], manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    record_by_identity = {str(row["identity"]): row for row in records}
    identities = manifest["identity_manifest"]
    results: list[dict[str, Any]] = []
    for coordinate in manifest["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        coordinate_identities = [
            identity
            for identity, row in identities.items()
            if row["coordinate_id"] == coordinate_id
        ]
        for observer_index, observer in enumerate(coordinate["observers"]):
            labels: list[int] = []
            blocks: list[int] = []
            vectors: list[list[float]] = []
            train_blocks: set[int] = set()
            eval_blocks: set[int] = set()
            widths = tuple(manifest["feature_contract"][f"{observer}_raw_widths"])
            for identity in coordinate_identities:
                frozen = identities[identity]
                record = record_by_identity[identity]
                labels.append(int(frozen["label"]))
                blocks.append(int(frozen["block"]))
                vectors.append(
                    timing_feature_vector(
                        record["observer_projections"][observer], raw_widths=widths
                    )
                )
                target = train_blocks if frozen["partition"] == "SENTINEL_TRAIN" else eval_blocks
                target.add(int(frozen["block"]))
            validate_matched_blocks(labels, blocks)
            if len(train_blocks) != 180 or len(eval_blocks) != 120 or train_blocks & eval_blocks:
                raise RuntimeError("sentinel TRAIN/EVAL block partition drifted")
            split = BlockSplit(tuple(sorted(train_blocks)), tuple(sorted(eval_blocks))).validate()
            selected = select_on_train_fit_predict_eval(
                vectors,
                labels,
                blocks,
                split,
                seed=int(coordinate["analysis_seed"]) + observer_index,
                cv_folds=5,
            )
            bootstrap = matched_block_bootstrap_auc_values(
                selected.eval_labels,
                selected.oriented_eval_scores,
                selected.eval_blocks,
                generator=np.random.default_rng(int(coordinate["bootstrap_seed"]) + observer_index),
                resamples=SENTINEL_BOOTSTRAP_RESAMPLES,
            )
            point = selected_model_eval_auc(
                selected.eval_labels, selected.oriented_eval_scores
            )
            ci_low, ci_high = np.quantile(bootstrap, [0.025, 0.975])
            lcb995 = float(np.quantile(bootstrap, SENTINEL_LCB_QUANTILE))
            randomization = paired_auc_randomization_test(
                selected.eval_labels,
                selected.oriented_eval_scores,
                selected.eval_blocks,
                seed=int(coordinate["randomization_seed"]) + observer_index,
                resamples=SENTINEL_RANDOMIZATION_RESAMPLES,
            )
            selected_diagnostic = selected.train_diagnostics[selected.selected_model]
            results.append(
                {
                    "task_id": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "selected_train_model": selected.selected_model,
                    "train_cv_raw_auc": selected_diagnostic.raw_train_cv_auc,
                    "train_score_orientation": selected.orientation,
                    "train_distinguishability_auc": selected_diagnostic.train_distinguishability_auc,
                    "eval_point_auc": point,
                    "eval_ci95_two_sided_low": float(ci_low),
                    "eval_ci95_two_sided_high": float(ci_high),
                    "eval_lcb99_5_one_sided": lcb995,
                    "early_fail": lcb995 > SENTINEL_EARLY_FAIL_MARGIN,
                    "train_blocks": selected.train_block_count,
                    "eval_blocks": selected.eval_block_count,
                    "train_sessions": selected.train_sample_count,
                    "eval_sessions": selected.eval_sample_count,
                    "bootstrap_resamples": SENTINEL_BOOTSTRAP_RESAMPLES,
                    "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
                    "model_refit_inside_bootstrap": False,
                    "orientation_reselected_inside_bootstrap": False,
                    "randomization": randomization,
                    "all_train_model_diagnostics": {
                        name: {
                            "raw_train_cv_auc": diagnostic.raw_train_cv_auc,
                            "orientation": diagnostic.orientation,
                            "train_distinguishability_auc": diagnostic.train_distinguishability_auc,
                        }
                        for name, diagnostic in selected.train_diagnostics.items()
                    },
                }
            )
    if len(results) != 10:
        raise RuntimeError("sentinel analysis did not produce exactly ten observer comparisons")
    return results


def _platform_diagnostics(records: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "launch_slip_ns",
        "relay_request_gap_ns",
        "relay_response_send_gap_ns",
        "registry_query_gap_ns",
        "registry_request_response_ns",
    )
    result = {
        key: distribution(
            value
            for record in records
            for value in record["platform_diagnostics"][key]
        )
        for key in keys
    }
    result["nominal_late_cell_count"] = sum(
        int(record["platform_diagnostics"]["nominal_late_cells"]) for record in records
    )
    result["liveness_failures"] = sum(
        bool(record["platform_diagnostics"]["infrastructure_liveness_failure"])
        for record in records
    )
    result["outlier_removal"] = "NONE"
    result["winsorization"] = "NONE"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one closed frozen P10 sentinel dataset.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite sentinel analysis: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != manifest["execution_source_commit"]:
        raise RuntimeError("analysis repository commit differs from frozen execution source")
    for relative, expected in manifest["analysis_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"analysis source hash mismatch: {relative}")
    records = _verify_closed_dataset(args.input, manifest)
    args.output.mkdir(parents=True)
    results = _analysis_rows(records, manifest)
    early_failures = [row for row in results if row["early_fail"]]
    verdict = "EARLY_FAIL" if early_failures else "PASS_TO_FULL"
    report = {
        "schema": "AgentTool.V12P10TimingSentinelAnalysis/1",
        "phase": "V12-P10-TIMING-SENTINEL-DEVELOPMENT",
        "protocol_base_sha": manifest["protocol_base_sha"],
        "execution_source_commit": manifest["execution_source_commit"],
        "frozen_manifest_sha256": sha256(args.manifest),
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "P10_functional": "ELIGIBLE_PRESERVED",
        "P10_sentinel_sessions": 4800,
        "P10_sentinel_retries": 0,
        "observer_comparisons": 10,
        "early_fail_rule": "ANY one-sided complete-block bootstrap LCB99.5 > 0.55",
        "privacy_pass_authority": False,
        "P10_sentinel": verdict,
        "early_fail_comparisons": [
            {
                "task_id": row["task_id"],
                "framework": row["framework"],
                "observer": row["observer"],
                "lcb99_5": row["eval_lcb99_5_one_sided"],
            }
            for row in early_failures
        ],
        "comparisons": results,
        "platform_diagnostics": _platform_diagnostics(records),
        "P10_full": "NOT_RUN",
        "P20_sentinel": "NOT_RUN",
        "P20_full": "NOT_RUN",
        "P25_sentinel": "NOT_RUN",
        "P25_full": "NOT_RUN",
        "selected_timing_delta_ms": "NONE",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "timing_confirmatory_sessions": 0,
        "final_b4_b5": "NOT_RUN",
        "final_candidate_universe_exists": "NO",
        "final_seed_exists": "NO",
        "selected_final_v12_cases_executed": 0,
        "ready_for_P10_full_development": verdict == "PASS_TO_FULL",
        "ready_for_timing_confirmatory": "NO",
        "ready_for_final_v12_holdout": "NO",
    }
    write_json(args.output / "p10_sentinel_analysis.json", report)
    with (args.output / "p10_sentinel_comparisons.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "task_id",
                "framework",
                "observer",
                "selected_train_model",
                "train_cv_raw_auc",
                "train_score_orientation",
                "eval_point_auc",
                "eval_ci95_two_sided_low",
                "eval_ci95_two_sided_high",
                "eval_lcb99_5_one_sided",
                "early_fail",
                "train_blocks",
                "eval_blocks",
                "randomization_p",
            ),
        )
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    **{key: row[key] for key in writer.fieldnames if key != "randomization_p"},
                    "randomization_p": row["randomization"]["one_sided_randomization_p"],
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
