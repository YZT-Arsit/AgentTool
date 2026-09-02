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
)
from v12_timing.sentinel_resume import (
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)
from v12_timing.statistics import (
    BlockSplit,
    matched_block_bootstrap_auc_values,
    paired_auc_randomization_test,
    selected_model_eval_auc,
    validate_matched_blocks,
)

ANALYSIS_SCHEMA = "AgentTool.V12P10TimingSentinelResumeAnalysis/1"
ANALYSIS_PHASE = "V12-P10-TIMING-DISTINGUISHABILITY-SENTINEL-RESUME"
ANALYSIS_FILENAME = "sentinel_resume_analysis.json"
COMPARISONS_FILENAME = "observer_comparisons.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def quantile(values: Iterable[int], probability: float) -> int:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        return 0
    return ordered[
        min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))
    ]


def distribution(values: Iterable[int]) -> dict[str, int]:
    rows = list(values)
    return {
        "count": len(rows),
        "p50": quantile(rows, 0.50),
        "p95": quantile(rows, 0.95),
        "p99": quantile(rows, 0.99),
        "max": max(rows, default=0),
    }


def _verify_closed_dataset(
    campaign_root: Path, manifest: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    completion = json.loads(
        (campaign_root / "campaign_completion.json").read_text(encoding="utf-8")
    )
    dataset = json.loads(
        (campaign_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    if completion.get("status") != "COLLECTION_CLOSED_COMPLETE":
        raise RuntimeError(
            "resume sentinel analysis requires a closed complete collection"
        )
    if int(completion.get("executed_sessions", -1)) != TOTAL_SESSIONS:
        raise RuntimeError("resume sentinel collection denominator failed")
    if int(completion.get("retries", -1)) != 0:
        raise RuntimeError("resume sentinel collection violated zero-retry policy")
    if dataset.get("collection_closed") is not True or dataset.get(
        "common_integrity_abort"
    ):
        raise RuntimeError("resume sentinel dataset is not validly closed")
    if int(dataset.get("session_record_count", -1)) != TOTAL_SESSIONS:
        raise RuntimeError("resume sentinel dataset manifest is incomplete")
    if dataset.get("frozen_manifest_sha256") != sha256(
        campaign_root / "frozen_manifest.json"
    ):
        raise RuntimeError("resume sentinel frozen manifest hash drifted")
    records: list[dict[str, Any]] = []
    for row in dataset["session_records"]:
        path = campaign_root / row["path"]
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"resume sentinel session record hash mismatch: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") != row["status"]:
            raise RuntimeError("resume sentinel status inventory drifted")
        records.append(record)
    identities = {str(row["identity"]) for row in records}
    if (
        identities != set(manifest["identity_manifest"])
        or len(identities) != TOTAL_SESSIONS
    ):
        raise RuntimeError("resume sentinel closed dataset identity inventory drifted")
    return records, dataset


def _analysis_rows(
    records: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    record_by_identity = {str(row["identity"]): row for row in records}
    identities = manifest["identity_manifest"]
    results: list[dict[str, Any]] = []
    for coordinate in manifest["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        chosen = selection[coordinate_id]
        if not all(
            chosen[partition]["sufficient"]
            for partition in ("SENTINEL_TRAIN", "SENTINEL_EVAL")
        ):
            for observer in coordinate["observers"]:
                results.append(
                    {
                        "task_id": coordinate["task_id"],
                        "framework": coordinate["framework"],
                        "observer": observer,
                        "status": "NOT_EVALUABLE_INSUFFICIENT_COMPLETE_BLOCKS",
                        "selected_train_blocks": len(
                            chosen["SENTINEL_TRAIN"]["selected_planned_blocks"]
                        ),
                        "selected_eval_blocks": len(
                            chosen["SENTINEL_EVAL"]["selected_planned_blocks"]
                        ),
                    }
                )
            continue
        selected_identity_set = set(chosen["SENTINEL_TRAIN"]["selected_identities"])
        selected_identity_set.update(chosen["SENTINEL_EVAL"]["selected_identities"])
        coordinate_identities = sorted(
            selected_identity_set,
            key=lambda identity: (
                int(identities[identity]["planned_block"]),
                int(identities[identity]["label"]),
            ),
        )
        train_blocks = set(chosen["SENTINEL_TRAIN"]["selected_planned_blocks"])
        eval_blocks = set(chosen["SENTINEL_EVAL"]["selected_planned_blocks"])
        if (
            len(train_blocks) != TARGET_TRAIN_COMPLETE_BLOCKS
            or len(eval_blocks) != TARGET_EVAL_COMPLETE_BLOCKS
        ):
            raise RuntimeError(
                "resume sentinel selected complete-block denominator drifted"
            )
        if train_blocks & eval_blocks:
            raise RuntimeError("resume sentinel selected TRAIN/EVAL blocks overlap")
        for observer_index, observer in enumerate(coordinate["observers"]):
            labels: list[int] = []
            blocks: list[int] = []
            vectors: list[list[float]] = []
            widths = tuple(manifest["feature_contract"][f"{observer}_raw_widths"])
            for identity in coordinate_identities:
                frozen = identities[identity]
                record = record_by_identity[identity]
                if (
                    record["status"] != "COMPLETE"
                    or not record["timing_classifier_eligible"]
                ):
                    raise RuntimeError(
                        "selected timing block contains an incomplete session"
                    )
                if record.get("failure_category") is not None:
                    raise RuntimeError(
                        "failure status entered the timing classifier dataset"
                    )
                labels.append(int(frozen["label"]))
                blocks.append(int(frozen["planned_block"]))
                vectors.append(
                    timing_feature_vector(
                        record["observer_projections"][observer], raw_widths=widths
                    )
                )
            validate_matched_blocks(labels, blocks)
            split = BlockSplit(
                tuple(sorted(train_blocks)), tuple(sorted(eval_blocks))
            ).validate()
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
                generator=np.random.default_rng(
                    int(coordinate["bootstrap_seed"]) + observer_index
                ),
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
            diagnostic = selected.train_diagnostics[selected.selected_model]
            results.append(
                {
                    "task_id": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "status": "EVALUATED",
                    "selected_train_model": selected.selected_model,
                    "train_cv_raw_auc": diagnostic.raw_train_cv_auc,
                    "train_score_orientation": selected.orientation,
                    "train_distinguishability_auc": diagnostic.train_distinguishability_auc,
                    "eval_point_auc": point,
                    "eval_ci95_two_sided_low": float(ci_low),
                    "eval_ci95_two_sided_high": float(ci_high),
                    "eval_lcb99_5_one_sided": lcb995,
                    "early_fail": lcb995 > SENTINEL_EARLY_FAIL_MARGIN,
                    "train_blocks": selected.train_block_count,
                    "eval_blocks": selected.eval_block_count,
                    "train_sessions": selected.train_sample_count,
                    "eval_sessions": selected.eval_sample_count,
                    "decisive_eval_model_count": selected.decisive_eval_model_count,
                    "bootstrap_resamples": SENTINEL_BOOTSTRAP_RESAMPLES,
                    "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
                    "model_refit_inside_bootstrap": False,
                    "orientation_reselected_inside_bootstrap": False,
                    "randomization": randomization,
                    "all_train_model_diagnostics": {
                        name: {
                            "raw_train_cv_auc": value.raw_train_cv_auc,
                            "orientation": value.orientation,
                            "train_distinguishability_auc": value.train_distinguishability_auc,
                        }
                        for name, value in selected.train_diagnostics.items()
                    },
                }
            )
    expected_comparisons = int(manifest.get("observer_comparison_count", 10))
    if len(results) != expected_comparisons:
        raise RuntimeError(
            "sentinel analysis observer-comparison count drifted: "
            f"{len(results)} != {expected_comparisons}"
        )
    return results


def _platform_diagnostics(records: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [row for row in records if row["status"] == "COMPLETE"]
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
            for record in complete
            for value in record["platform_diagnostics"][key]
        )
        for key in keys
    }
    result["complete_session_count"] = len(complete)
    result["nominal_late_cell_count"] = sum(
        int(record["platform_diagnostics"]["nominal_late_cells"]) for record in complete
    )
    result["liveness_failures_among_complete"] = sum(
        bool(record["platform_diagnostics"]["infrastructure_liveness_failure"])
        for record in complete
    )
    response_slips = [
        int(value)
        for record in complete
        for value in record["platform_diagnostics"].get(
            "response_release_slip_ns", []
        )
    ]
    result["response_deadline_miss_count"] = sum(
        int(record["platform_diagnostics"].get("response_deadline_miss_count", 0))
        for record in complete
    )
    result["response_release_slip_ns"] = distribution(response_slips)
    result["maximum_response_release_slip_ns"] = max(response_slips, default=0)
    result["response_deadline_miss_is_diagnostic_only"] = True
    result["outlier_removal"] = "NONE"
    result["winsorization"] = "NONE"
    result["role"] = "PLATFORM_DIAGNOSTIC_NOT_CLASSIFIER_FEATURE"
    return result


def _combined_verdict(
    completion: list[dict[str, Any]],
    selection: Mapping[str, Any],
    results: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    insufficient = any(
        not partition["sufficient"]
        for coordinate in selection.values()
        for partition in coordinate.values()
    )
    failure_concern = any(row["failure_channel_flag"] for row in completion)
    operational_concern = any(
        row["operational_reliability_concern"] for row in completion
    )
    evaluated = [row for row in results if row["status"] == "EVALUATED"]
    if insufficient:
        return "INSUFFICIENT_COMPLETE_BLOCKS", "NOT_EVALUABLE", False
    timing = (
        "EARLY_FAIL" if any(row["early_fail"] for row in evaluated) else "PASS_TO_FULL"
    )
    if failure_concern:
        return "FAILURE_CHANNEL_CONCERN", timing, False
    if operational_concern:
        return "OPERATIONAL_RELIABILITY_CONCERN", timing, False
    if timing == "EARLY_FAIL":
        return "EARLY_TIMING_DISTINGUISHABILITY", timing, False
    return "PASS_TO_FULL", timing, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze one closed fresh P10 resume sentinel."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite resume sentinel analysis: {args.output}"
        )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != manifest["execution_source_commit"]:
        raise RuntimeError(
            "analysis repository commit differs from frozen execution source"
        )
    for relative, expected in manifest["analysis_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"analysis source hash mismatch: {relative}")
    records, dataset = _verify_closed_dataset(args.input, manifest)
    status_by_identity = {str(row["identity"]): str(row["status"]) for row in records}
    completion = completion_channel(manifest, status_by_identity)
    selection = select_complete_blocks(manifest, status_by_identity)
    args.output.mkdir(parents=True)
    write_json(args.output / "completion_channel.json", completion)
    write_json(args.output / "selected_complete_blocks.json", selection)
    results = _analysis_rows(records, manifest, selection)
    verdict, timing_verdict, ready = _combined_verdict(completion, selection, results)
    report = {
        "schema": ANALYSIS_SCHEMA,
        "phase": ANALYSIS_PHASE,
        "protocol_base_sha": manifest["protocol_base_sha"],
        "latest_development_evidence_sha": manifest["latest_development_evidence_sha"],
        "execution_source_commit": manifest["execution_source_commit"],
        "frozen_manifest_sha256": sha256(args.manifest),
        "dataset_manifest_sha256": sha256(args.input / "dataset_manifest.json"),
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "old_sentinel": "PERMANENTLY_ABORTED_AND_SEALED",
        "old_failed_identity_reexecuted": False,
        "P10_functional": "ELIGIBLE_PRESERVED",
        "planned_sessions": TOTAL_SESSIONS,
        "executed_sessions": TOTAL_SESSIONS,
        "complete_sessions": sum(row["status"] == "COMPLETE" for row in records),
        "failed_sessions": sum(row["status"] == "FAILED" for row in records),
        "retries": 0,
        "completion_channel": completion,
        "complete_block_selection": selection,
        "observer_comparisons": results,
        "P10_sentinel_timing": timing_verdict,
        "P10_sentinel": verdict,
        "ready_for_P10_full_development": ready,
        "sentinel_privacy_pass_authority": False,
        "classifier_training_during_collection": 0,
        "AUC_calculations_during_collection": 0,
        "protected_analysis_runs_after_collection_close": 1,
        "P10_full": "NOT_RUN",
        "P20_sentinel": "NOT_RUN",
        "P25_sentinel": "NOT_RUN",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "timing_confirmatory_sessions": 0,
        "final_v12_cases_executed": 0,
        "platform_diagnostics": _platform_diagnostics(records),
    }
    write_json(args.output / ANALYSIS_FILENAME, report)
    with (args.output / COMPARISONS_FILENAME).open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = (
            "task_id",
            "framework",
            "observer",
            "status",
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
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(
        json.dumps(
            {
                "P10_sentinel": verdict,
                "P10_sentinel_timing": timing_verdict,
                "complete_sessions": report["complete_sessions"],
                "failed_sessions": report["failed_sessions"],
                "ready_for_P10_full_development": ready,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
