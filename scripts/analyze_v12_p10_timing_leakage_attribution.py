from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import analyze_v12_p10_timing_sentinel_resume as implementation  # noqa: E402

from v12_timing.attribution import (  # noqa: E402
    dominant_timing_source,
    expected_family_widths,
    feature_family_vector,
    observer_feature_families,
)
from v12_timing.classifier import select_on_train_fit_predict_eval  # noqa: E402
from v12_timing.sentinel import (  # noqa: E402
    SENTINEL_BOOTSTRAP_RESAMPLES,
    SENTINEL_LCB_QUANTILE,
)
from v12_timing.sentinel_v3 import (  # noqa: E402
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)
from v12_timing.statistics import (  # noqa: E402
    BlockSplit,
    matched_block_bootstrap_auc_values,
    selected_model_eval_auc,
    validate_matched_blocks,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.TARGET_TRAIN_COMPLETE_BLOCKS = TARGET_TRAIN_COMPLETE_BLOCKS
implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.completion_channel = completion_channel
implementation.select_complete_blocks = select_complete_blocks
implementation.validate_freeze_manifest = validate_freeze_manifest

BASE_RESULT_SHA = "558c97bd5ca8bb9123382800cb73eb410cab6342"
METHODOLOGY_BASE_SHA = "63792088161deb6b1ccd3c4b4cb28babbf72f3ec"
ROLE = "POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC"
EARLY_FAIL_MARGIN = 0.55


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _git_preflight() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_RESULT_SHA, head],
        cwd=ROOT,
        check=True,
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{BASE_RESULT_SHA}..{head}"],
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
        "v12_timing/classifier.py",
        "v12_timing/projection.py",
        "v12_timing/statistics.py",
        "v12_timing/scheduler.py",
        "v12_timing/pacer.py",
    }
    forbidden = [
        path
        for path in changed
        if path in protected_exact or path.startswith(protected_prefixes)
    ]
    if forbidden:
        raise RuntimeError(
            f"protected runtime/statistical machinery diff is not NONE: {forbidden}"
        )
    return head


def _selected_coordinate_identities(
    coordinate_id: str,
    selection: dict[str, Any],
    frozen_identities: dict[str, Any],
) -> tuple[list[str], set[int], set[int]]:
    chosen = selection[coordinate_id]
    train_blocks = set(chosen["SENTINEL_TRAIN"]["selected_planned_blocks"])
    eval_blocks = set(chosen["SENTINEL_EVAL"]["selected_planned_blocks"])
    selected = set(chosen["SENTINEL_TRAIN"]["selected_identities"])
    selected.update(chosen["SENTINEL_EVAL"]["selected_identities"])
    identities = sorted(
        selected,
        key=lambda identity: (
            int(frozen_identities[identity]["planned_block"]),
            int(frozen_identities[identity]["label"]),
        ),
    )
    return identities, train_blocks, eval_blocks


def _immutable_all_result(
    original: dict[str, Any], family: str, width: int
) -> dict[str, Any]:
    diagnostic = original["all_train_model_diagnostics"][
        original["selected_train_model"]
    ]
    return {
        "feature_family": family,
        "feature_width": width,
        "result_origin": "IMMUTABLE_ORIGINAL_V3_1_RESULT_REUSED",
        "selected_model": original["selected_train_model"],
        "train_cv_raw_auc": diagnostic["raw_train_cv_auc"],
        "train_orientation": diagnostic["orientation"],
        "train_distinguishability_auc": diagnostic["train_distinguishability_auc"],
        "eval_auc": original["eval_point_auc"],
        "eval_ci95_low": original["eval_ci95_two_sided_low"],
        "eval_ci95_high": original["eval_ci95_two_sided_high"],
        "eval_lcb99_5": original["eval_lcb99_5_one_sided"],
        "frozen_boundary_exceeded": original["eval_lcb99_5_one_sided"]
        > EARLY_FAIL_MARGIN,
        "train_blocks": original["train_blocks"],
        "eval_blocks": original["eval_blocks"],
        "bootstrap_resamples": original["bootstrap_resamples"],
        "all_train_model_diagnostics": original["all_train_model_diagnostics"],
    }


def _observer_attribution(
    records: list[dict[str, Any]],
    freeze: dict[str, Any],
    selection: dict[str, Any],
    original_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    record_by_identity = {str(row["identity"]): row for row in records}
    frozen_identities = freeze["identity_manifest"]
    original_by_key = {
        (row["task_id"], row["framework"], row["observer"]): row
        for row in original_report["observer_comparisons"]
    }
    results: list[dict[str, Any]] = []
    dominant: dict[str, str] = {}
    for coordinate in freeze["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        identities, train_blocks, eval_blocks = _selected_coordinate_identities(
            coordinate_id, selection, frozen_identities
        )
        for observer_index, observer in enumerate(coordinate["observers"]):
            key = (coordinate["task_id"], coordinate["framework"], observer)
            original = original_by_key[key]
            widths = tuple(
                int(value)
                for value in freeze["feature_contract"][f"{observer}_raw_widths"]
            )
            expected_widths = expected_family_widths(observer, widths)
            labels = [
                int(frozen_identities[identity]["label"]) for identity in identities
            ]
            blocks = [
                int(frozen_identities[identity]["planned_block"])
                for identity in identities
            ]
            projections = [
                record_by_identity[identity]["observer_projections"][observer]
                for identity in identities
            ]
            validate_matched_blocks(labels, blocks)
            split = BlockSplit(
                tuple(sorted(train_blocks)), tuple(sorted(eval_blocks))
            ).validate()
            comparison_rows: list[dict[str, Any]] = []
            for family in observer_feature_families(observer):
                if family.endswith("_ALL"):
                    family_result = _immutable_all_result(
                        original, family, expected_widths[family]
                    )
                else:
                    vectors = [
                        feature_family_vector(
                            projection, raw_widths=widths, family=family
                        )
                        for projection in projections
                    ]
                    if {len(vector) for vector in vectors} != {expected_widths[family]}:
                        raise RuntimeError("diagnostic feature-family width drifted")
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
                    lcb = float(np.quantile(bootstrap, SENTINEL_LCB_QUANTILE))
                    selected_diagnostic = selected.train_diagnostics[
                        selected.selected_model
                    ]
                    family_result = {
                        "feature_family": family,
                        "feature_width": expected_widths[family],
                        "result_origin": ROLE,
                        "selected_model": selected.selected_model,
                        "train_cv_raw_auc": selected_diagnostic.raw_train_cv_auc,
                        "train_orientation": selected.orientation,
                        "train_distinguishability_auc": selected_diagnostic.train_distinguishability_auc,
                        "eval_auc": point,
                        "eval_ci95_low": float(ci_low),
                        "eval_ci95_high": float(ci_high),
                        "eval_lcb99_5": lcb,
                        "frozen_boundary_exceeded": lcb > EARLY_FAIL_MARGIN,
                        "train_blocks": selected.train_block_count,
                        "eval_blocks": selected.eval_block_count,
                        "bootstrap_resamples": SENTINEL_BOOTSTRAP_RESAMPLES,
                        "all_train_model_diagnostics": {
                            name: {
                                "raw_train_cv_auc": value.raw_train_cv_auc,
                                "orientation": value.orientation,
                                "train_distinguishability_auc": value.train_distinguishability_auc,
                            }
                            for name, value in selected.train_diagnostics.items()
                        },
                    }
                row = {
                    "role": ROLE,
                    "coordinate_id": coordinate_id,
                    "task": coordinate["task_id"],
                    "framework": coordinate["framework"],
                    "observer": observer,
                    "original_early_failure": bool(original["early_fail"]),
                    **family_result,
                }
                results.append(row)
                comparison_rows.append(row)
            if original["early_fail"]:
                lcb_by_family = {
                    row["feature_family"]: float(row["eval_lcb99_5"])
                    for row in comparison_rows
                }
                dominant["|".join(map(str, key))] = dominant_timing_source(
                    observer, lcb_by_family
                )
    if len(results) != 50:
        raise RuntimeError("attribution did not produce 50 fixed family comparisons")
    if len(dominant) != 6:
        raise RuntimeError("original early-failure inventory changed")
    return results, dominant


def _relay_slot_tables(
    records: list[dict[str, Any]],
    freeze: dict[str, Any],
    selection: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    record_by_identity = {str(row["identity"]): row for row in records}
    frozen_identities = freeze["identity_manifest"]
    rows: list[dict[str, Any]] = []
    top: dict[str, Any] = {}
    metrics = {
        "request_relative_ns": "slot_indexed_session_relative_request_ns",
        "response_send_relative_ns": "slot_indexed_session_relative_response_send_ns",
        "request_response_latency_ns": "slot_paired_request_response_ns",
    }
    for coordinate in freeze["physical_coordinates"]:
        if (
            coordinate["task_id"] not in {"T7", "T9"}
            or "RELAY" not in coordinate["observers"]
        ):
            continue
        coordinate_id = str(coordinate["coordinate_id"])
        identities, _, _ = _selected_coordinate_identities(
            coordinate_id, selection, frozen_identities
        )
        projections = {
            label: [
                record_by_identity[identity]["observer_projections"]["RELAY"]
                for identity in identities
                if int(frozen_identities[identity]["label"]) == label
            ]
            for label in (0, 1)
        }
        coordinate_rows = []
        for slot_index in range(506):
            row: dict[str, Any] = {
                "role": ROLE,
                "coordinate_id": coordinate_id,
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "public_slot": slot_index + 1,
                "selected_sessions_per_class": len(projections[0]),
            }
            for metric, key in metrics.items():
                medians = {
                    label: float(
                        np.median(
                            [
                                projection[key][slot_index]
                                for projection in projections[label]
                            ]
                        )
                    )
                    for label in (0, 1)
                }
                row[f"class0_median_{metric}"] = medians[0]
                row[f"class1_median_{metric}"] = medians[1]
                row[f"class1_minus_class0_{metric}"] = medians[1] - medians[0]
            rows.append(row)
            coordinate_rows.append(row)
        top[coordinate_id] = {
            metric: [
                {
                    "public_slot": row["public_slot"],
                    "class1_minus_class0_ns": row[f"class1_minus_class0_{metric}"],
                }
                for row in sorted(
                    coordinate_rows,
                    key=lambda value: abs(value[f"class1_minus_class0_{metric}"]),
                    reverse=True,
                )[:20]
            ]
            for metric in metrics
        }
    if len(rows) != 4 * 506:
        raise RuntimeError("Relay slot table did not cover four T7/T9 coordinates")
    return rows, top


def _median_sequences(sequences: list[list[int]]) -> list[float]:
    width = max((len(sequence) for sequence in sequences), default=0)
    return [
        float(
            np.median(
                [sequence[index] for sequence in sequences if len(sequence) > index]
            )
        )
        for index in range(width)
    ]


def _private_mechanism_correlation(
    records: list[dict[str, Any]],
    dataset: dict[str, Any],
    campaign_root: Path,
    freeze: dict[str, Any],
    selection: dict[str, Any],
    slot_top: dict[str, Any],
) -> dict[str, Any]:
    record_by_identity = {str(row["identity"]): row for row in records}
    unit_by_identity: dict[str, Path] = {}
    for inventory in dataset["session_records"]:
        path = campaign_root / str(inventory["path"])
        record = json.loads(path.read_text(encoding="utf-8"))
        unit_by_identity[str(record["identity"])] = path.parent
    frozen_identities = freeze["identity_manifest"]
    relay: dict[str, Any] = {}
    registry: dict[str, Any] = {}
    for coordinate in freeze["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        identities, _, _ = _selected_coordinate_identities(
            coordinate_id, selection, frozen_identities
        )
        if coordinate["task_id"] in {"T7", "T9"} and "RELAY" in coordinate["observers"]:
            by_label: dict[int, dict[str, list[list[int]]]] = {
                label: defaultdict(list) for label in (0, 1)
            }
            for identity in identities:
                label = int(frozen_identities[identity]["label"])
                go_result = json.loads(
                    (unit_by_identity[identity] / "go_online_result.json").read_text(
                        encoding="utf-8"
                    )
                )
                events = go_result.get("private_events", [])
                for stage, key in (
                    ("ACCEPTED", "action_admission_rounds"),
                    ("PROVIDER_CALL_BEGIN", "provider_start_rounds"),
                    ("CLIENT_BHTTP_DECODED", "result_delivery_rounds"),
                ):
                    by_label[label][key].append(
                        sorted(
                            int(row["round"])
                            for row in events
                            if row.get("stage") == stage
                        )
                    )
            label_summary = {
                str(label): {
                    key: {
                        "session_count": len(values),
                        "nonempty_session_count": sum(bool(value) for value in values),
                        "median_round_by_causal_position": _median_sequences(values),
                    }
                    for key, values in by_label[label].items()
                }
                for label in (0, 1)
            }
            transition_rounds = [
                value
                for summary in label_summary.values()
                for stage in ("action_admission_rounds", "result_delivery_rounds")
                for value in summary.get(stage, {}).get(
                    "median_round_by_causal_position", []
                )
            ]
            top_alignment = {}
            for metric, values in slot_top[coordinate_id].items():
                top_alignment[metric] = {
                    "minimum_distance_from_top20_slots_to_any_median_transition_round": min(
                        abs(int(row["public_slot"]) - transition)
                        for row in values
                        for transition in transition_rounds
                    )
                    if transition_rounds
                    else None,
                    "top20_slots_within_two_rounds_of_median_transition": sum(
                        any(
                            abs(int(row["public_slot"]) - transition) <= 2
                            for transition in transition_rounds
                        )
                        for row in values
                    ),
                }
            relay[coordinate_id] = {
                "role": "PRIVATE_DEVELOPMENT_DIAGNOSTIC_NOT_OBSERVER_FEATURE",
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "labels": label_summary,
                "top_slot_transition_alignment": top_alignment,
            }
        if (
            coordinate["task_id"] in {"C1_REGISTRY_RESOLUTION_PATTERN", "T7"}
            and "REGISTRY" in coordinate["observers"]
        ):
            by_label_values: dict[int, dict[str, list[int]]] = {
                label: {"real": [], "dummy": []} for label in (0, 1)
            }
            real_ordinal_counts: dict[int, list[int]] = {
                label: [0] * 100 for label in (0, 1)
            }
            for identity in identities:
                label = int(frozen_identities[identity]["label"])
                cover = json.loads(
                    (
                        unit_by_identity[identity]
                        / "pir"
                        / "private_pir_cover_schedule.json"
                    ).read_text(encoding="utf-8")
                )
                latencies = record_by_identity[identity]["observer_projections"][
                    "REGISTRY"
                ]["query_response_ns"]
                if len(cover) != 100 or len(latencies) != 100:
                    raise RuntimeError(
                        "Registry private correlation schedule width drifted"
                    )
                for ordinal, (private_row, latency) in enumerate(
                    zip(cover, latencies, strict=True)
                ):
                    kind = "real" if bool(private_row["real"]) else "dummy"
                    by_label_values[label][kind].append(int(latency))
                    if kind == "real":
                        real_ordinal_counts[label][ordinal] += 1
            registry[coordinate_id] = {
                "role": "PRIVATE_DEVELOPMENT_DIAGNOSTIC_NOT_OBSERVER_FEATURE",
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "labels": {
                    str(label): {
                        kind: {
                            "observation_count": len(by_label_values[label][kind]),
                            "median_query_response_ns": float(
                                np.median(by_label_values[label][kind])
                            )
                            if by_label_values[label][kind]
                            else None,
                        }
                        for kind in ("real", "dummy")
                    }
                    for label in (0, 1)
                },
                "highest_real_query_ordinal_frequencies": {
                    str(label): [
                        {"ordinal": ordinal, "real_session_count": count}
                        for ordinal, count in sorted(
                            enumerate(real_ordinal_counts[label]),
                            key=lambda item: item[1],
                            reverse=True,
                        )[:12]
                        if count
                    ]
                    for label in (0, 1)
                },
            }
    return {
        "role": "PRIVATE_DEVELOPMENT_DIAGNOSTIC_NOT_OBSERVER_FEATURE",
        "performed_after_observer_only_attribution": True,
        "relay": relay,
        "registry": registry,
    }


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "role",
        "coordinate_id",
        "task",
        "framework",
        "observer",
        "original_early_failure",
        "feature_family",
        "feature_width",
        "result_origin",
        "selected_model",
        "train_cv_raw_auc",
        "train_orientation",
        "train_distinguishability_auc",
        "eval_auc",
        "eval_ci95_low",
        "eval_ci95_high",
        "eval_lcb99_5",
        "frozen_boundary_exceeded",
        "train_blocks",
        "eval_blocks",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_slot_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-outcome P10 timing leakage attribution."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--analysis-input-manifest", type=Path, required=True)
    parser.add_argument("--original-results", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite leakage-attribution output: {args.output}"
        )
    head = _git_preflight()
    freeze = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(freeze)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    frozen_input = json.loads(args.analysis_input_manifest.read_text(encoding="utf-8"))
    original = json.loads(args.original_results.read_text(encoding="utf-8"))
    if protocol["role"] != ROLE or protocol["base_p10_result"] != BASE_RESULT_SHA:
        raise RuntimeError("wrong attribution protocol")
    for relative, expected in protocol["analysis_source_hashes"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"attribution source hash mismatch: {relative}")
    if (
        sha256(args.analysis_input_manifest)
        != protocol["analysis_input_manifest_sha256"]
    ):
        raise RuntimeError("analysis input manifest hash changed")
    if sha256(args.original_results) != protocol["original_result_sha256"]:
        raise RuntimeError("immutable original P10 result hash changed")
    if original["P10_sentinel"] != "EARLY_TIMING_DISTINGUISHABILITY":
        raise RuntimeError("original P10 sentinel result changed")
    if sum(bool(row["early_fail"]) for row in original["observer_comparisons"]) != 6:
        raise RuntimeError("original early-failure inventory changed")
    records, dataset = implementation._verify_closed_dataset(args.input, freeze)
    if (
        len(records) != 5040
        or sum(row["status"] == "COMPLETE" for row in records) != 5025
    ):
        raise RuntimeError("closed dataset inventory changed")
    if sum(row["status"] == "FAILED" for row in records) != 15:
        raise RuntimeError("closed dataset failure inventory changed")
    if (
        sha256(args.input / "dataset_manifest.json")
        != frozen_input["dataset_manifest_sha256"]
    ):
        raise RuntimeError("closed dataset manifest hash changed")
    statuses = {str(row["identity"]): str(row["status"]) for row in records}
    selection = select_complete_blocks(freeze, statuses)
    if selection != frozen_input["selection"]:
        raise RuntimeError("complete-block selection changed")
    args.output.mkdir(parents=True)
    family_rows, dominant = _observer_attribution(records, freeze, selection, original)
    write_json(
        args.output / "observer_feature_family_results.json",
        {
            "schema": "AgentTool.V12P10TimingLeakageAttributionObserverFamilies/1",
            "role": ROLE,
            "rows": family_rows,
        },
    )
    _write_results_csv(args.output / "observer_feature_family_results.csv", family_rows)
    slot_rows, slot_top = _relay_slot_tables(records, freeze, selection)
    _write_slot_csv(args.output / "relay_slot_class_medians.csv", slot_rows)
    write_json(args.output / "relay_slot_top_differences.json", slot_top)
    private = _private_mechanism_correlation(
        records, dataset, args.input, freeze, selection, slot_top
    )
    write_json(args.output / "private_mechanism_correlation.json", private)
    sources = set(dominant.values())
    registry_response = any(
        source in {"RESPONSE_SIDE", "SLOT_LATENCY", "BOTH", "MIXED"}
        for key, source in dominant.items()
        if key.endswith("|REGISTRY")
    )
    relay_response = any(
        source in {"RESPONSE_SIDE", "SLOT_LATENCY", "BOTH", "MIXED"}
        for key, source in dominant.items()
        if key.endswith("|RELAY")
    )
    if registry_response and relay_response:
        recommendation = "MIXED_REDESIGN_REQUIRED"
    elif relay_response:
        recommendation = "RESPONSE_SHAPING_REQUIRED_BEFORE_MORE_DELTA_TESTING"
    elif registry_response:
        recommendation = "PIR_RESPONSE_SHAPING_REQUIRED"
    else:
        recommendation = "PROCEED_P20_UNMODIFIED"
    summary = {
        "schema": "AgentTool.V12P10TimingLeakageSourceAttribution/1",
        "role": ROLE,
        "base_p10_result": BASE_RESULT_SHA,
        "methodology_base": METHODOLOGY_BASE_SHA,
        "analysis_source_commit": head,
        "original_P10_sentinel": "EARLY_TIMING_DISTINGUISHABILITY",
        "original_early_failures": "6 / 10",
        "original_result_preserved": True,
        "new_protected_sessions": 0,
        "dataset_identity_count": 5040,
        "complete_sessions": 5025,
        "failed_sessions": 15,
        "selected_train_blocks_per_coordinate": 180,
        "selected_eval_blocks_per_coordinate": 120,
        "observer_feature_family_result_count": len(family_rows),
        "dominant_timing_sources": dominant,
        "dominant_source_categories_observed": sorted(sources),
        "relay_response_independently_paced": False,
        "registry_response_independently_paced": False,
        "next_step_recommendation": recommendation,
        "P20_sentinel": "NOT_RUN",
        "P25_sentinel": "NOT_RUN",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "protected_runtime_diff": "NONE",
        "private_mechanism_correlation_file": "private_mechanism_correlation.json",
        "observer_family_results_file": "observer_feature_family_results.json",
        "relay_slot_table_file": "relay_slot_class_medians.csv",
    }
    write_json(args.output / "attribution_summary.json", summary)
    print(
        json.dumps(
            {
                "dominant_timing_sources": dominant,
                "next_step_recommendation": recommendation,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
