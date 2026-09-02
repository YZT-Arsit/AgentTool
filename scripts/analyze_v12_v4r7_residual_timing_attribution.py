from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.classifier import select_on_train_fit_predict_eval
from v12_timing.residual_attribution import (
    BOUNDARY_SLOT_KEYS,
    FEATURE_FAMILY_ORDER,
    attribution_feature_vectors,
    feature_family_contract,
)
from v12_timing.statistics import (
    BlockSplit,
    matched_block_bootstrap_auc_values,
    selected_model_eval_auc,
    validate_matched_blocks,
)

BASE_SMOKE = "f66649590f1159a5bce280baaea2cfdc3218435c"
BOOTSTRAP_RESAMPLES = 10_000
TARGET_COORDINATES = (
    "P10-T7-MS",
    "P10-T9-OA",
    "P10-T7-OA",
    "P10-T9-MS",
)
RESIDUAL_COORDINATES = ("P10-T7-MS", "P10-T9-OA")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite attribution evidence: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _load_archive_records(evidence: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    collection = evidence / "collection"
    dataset = json.loads((collection / "dataset_manifest.json").read_text(encoding="utf-8"))
    archive_path = collection / "session_records.tgz"
    records: list[dict[str, Any]] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        if len(members) != 640:
            raise RuntimeError("immutable archive does not contain exactly 640 records")
        for row in dataset["session_records"]:
            member = members.get(str(row["path"]))
            if member is None:
                raise RuntimeError(f"archived session record missing: {row['path']}")
            handle = archive.extractfile(member)
            if handle is None:
                raise RuntimeError(f"cannot read archived session record: {row['path']}")
            raw = handle.read()
            if sha256_bytes(raw) != row["sha256"]:
                raise RuntimeError(f"archived session record hash mismatch: {row['path']}")
            records.append(json.loads(raw))
    if len({row["identity"] for row in records}) != 640:
        raise RuntimeError("archived identity inventory is not unique and complete")
    return records, dataset


def _selected_coordinate(
    analysis_input: dict[str, Any], coordinate_id: str
) -> dict[str, Any]:
    rows = {
        str(row["coordinate_id"]): row for row in analysis_input["coordinates"]
    }
    if coordinate_id not in rows:
        raise RuntimeError(f"selected-block inventory lacks {coordinate_id}")
    row = rows[coordinate_id]
    if len(row["train_block_ids"]) != 30 or len(row["eval_block_ids"]) != 30:
        raise RuntimeError("attribution must preserve the selected 30/30 denominator")
    return row


def _relay_analysis(
    records: list[dict[str, Any]],
    freeze: dict[str, Any],
    analysis_input: dict[str, Any],
    original: dict[str, Any],
) -> list[dict[str, Any]]:
    record_by_id = {str(row["identity"]): row for row in records}
    coordinates = {
        str(row["coordinate_id"]): row for row in freeze["physical_coordinates"]
    }
    original_rows = {
        (row["task_id"], row["framework"], row["observer"]): row
        for row in original["observer_comparisons"]
    }
    raw_widths = tuple(int(value) for value in freeze["feature_contract"]["RELAY_raw_widths"])
    output: list[dict[str, Any]] = []
    for coordinate_id in TARGET_COORDINATES:
        coordinate = coordinates[coordinate_id]
        selected = _selected_coordinate(analysis_input, coordinate_id)
        identity_ids = selected["train_identity_ids"] + selected["eval_identity_ids"]
        labels: list[int] = []
        blocks: list[int] = []
        family_vectors: dict[str, list[list[float]]] = {
            family: [] for family in FEATURE_FAMILY_ORDER
        }
        for identity in identity_ids:
            record = record_by_id[str(identity)]
            labels.append(int(record["label"]))
            blocks.append(int(record["planned_block"]))
            vectors = attribution_feature_vectors(
                record["observer_projections"]["RELAY"], raw_widths=raw_widths
            )
            for family in FEATURE_FAMILY_ORDER:
                family_vectors[family].append(vectors[family])
        validate_matched_blocks(labels, blocks)
        split = BlockSplit(
            tuple(sorted(int(value) for value in selected["train_block_ids"])),
            tuple(sorted(int(value) for value in selected["eval_block_ids"])),
        ).validate()
        observer_index = list(coordinate["observers"]).index("RELAY")
        model_seed = int(coordinate["analysis_seed"]) + observer_index
        bootstrap_seed = int(coordinate["bootstrap_seed"]) + observer_index
        for family in FEATURE_FAMILY_ORDER:
            fit = select_on_train_fit_predict_eval(
                family_vectors[family],
                labels,
                blocks,
                split,
                seed=model_seed,
                cv_folds=5,
            )
            bootstrap = matched_block_bootstrap_auc_values(
                fit.eval_labels,
                fit.oriented_eval_scores,
                fit.eval_blocks,
                generator=np.random.default_rng(bootstrap_seed),
                resamples=BOOTSTRAP_RESAMPLES,
            )
            diagnostic = fit.train_diagnostics[fit.selected_model]
            row = {
                "coordinate_id": coordinate_id,
                "task": coordinate["task_id"],
                "framework": coordinate["framework"],
                "observer": "RELAY",
                "role": (
                    "RESIDUAL_FOCUS"
                    if coordinate_id in RESIDUAL_COORDINATES
                    else "NEGATIVE_CONTROL"
                ),
                "feature_family": family,
                "feature_width": len(family_vectors[family][0]),
                "selected_model": fit.selected_model,
                "train_cv_raw_auc": diagnostic.raw_train_cv_auc,
                "train_orientation": fit.orientation,
                "train_distinguishability_auc": diagnostic.train_distinguishability_auc,
                "eval_auc": selected_model_eval_auc(
                    fit.eval_labels, fit.oriented_eval_scores
                ),
                "eval_ci95_low": float(np.quantile(bootstrap, 0.025)),
                "eval_ci95_high": float(np.quantile(bootstrap, 0.975)),
                "train_blocks": fit.train_block_count,
                "eval_blocks": fit.eval_block_count,
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "post_outcome_development_diagnostic": True,
            }
            if family == "ALL":
                original_row = original_rows[
                    (coordinate["task_id"], coordinate["framework"], "RELAY")
                ]
                if fit.selected_model != original_row["selected_train_model"] or not np.isclose(
                    row["eval_auc"], original_row["eval_point_auc"], atol=1e-15
                ):
                    raise RuntimeError("ALL family does not reproduce the immutable smoke result")
                row["reproduces_original_smoke_result"] = True
            output.append(row)
    return output


def _slot_medians(
    records: list[dict[str, Any]], analysis_input: dict[str, Any]
) -> list[dict[str, Any]]:
    record_by_id = {str(row["identity"]): row for row in records}
    output: list[dict[str, Any]] = []
    for coordinate_id in RESIDUAL_COORDINATES:
        selected = _selected_coordinate(analysis_input, coordinate_id)
        by_label: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for identity in selected["eval_identity_ids"]:
            record = record_by_id[str(identity)]
            by_label[int(record["label"])].append(record["observer_projections"]["RELAY"])
        if len(by_label[0]) != 30 or len(by_label[1]) != 30:
            raise RuntimeError("slot medians require the frozen 30/30 EVAL sessions")
        for slot in range(521):
            row: dict[str, Any] = {
                "coordinate_id": coordinate_id,
                "public_slot": slot + 1,
                "eval_sessions_per_class": 30,
            }
            for boundary, key in BOUNDARY_SLOT_KEYS.items():
                median0 = float(statistics.median(item[key][slot] for item in by_label[0]))
                median1 = float(statistics.median(item[key][slot] for item in by_label[1]))
                row[f"{boundary}_class0_median_ns"] = median0
                row[f"{boundary}_class1_median_ns"] = median1
                row[f"{boundary}_class1_minus_class0_median_ns"] = median1 - median0
            output.append(row)
    return output


def _percentiles(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "values_ns": [], "p50_ns": None, "p95_ns": None, "max_ns": None}
    return {
        "count": len(values),
        "values_ns": sorted(values),
        "p50_ns": float(np.quantile(values, 0.5)),
        "p95_ns": float(np.quantile(values, 0.95)),
        "max_ns": max(values),
    }


def _private_deadline_diagnostics(
    records: list[dict[str, Any]], freeze: dict[str, Any], raw_root: Path
) -> dict[str, Any]:
    record_by_id = {str(row["identity"]): row for row in records}
    identities = freeze["identity_manifest"]
    misses: list[dict[str, Any]] = []
    all_slips: dict[tuple[str, int], list[int]] = defaultdict(list)
    for dataset_row in json.loads(
        (raw_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )["session_records"]:
        identity = str(dataset_row["identity"])
        record = record_by_id[identity]
        relative = PurePosixPath(str(dataset_row["path"])).parent / "go_online_result.json"
        path = raw_root.joinpath(*relative.parts)
        if sha256(path) != record["raw_evidence_hashes"]["go_online_result.json"]:
            raise RuntimeError(f"private raw evidence hash mismatch: {identity}")
        runtime = json.loads(path.read_text(encoding="utf-8"))
        coordinate = str(identities[identity]["coordinate_id"])
        label = int(record["label"])
        for release in runtime["gateway_response_releases"]:
            slip = int(release["release_slip_ns"])
            all_slips[(coordinate, label)].append(slip)
            if bool(release["deadline_miss"]):
                misses.append(
                    {
                        "identity": identity,
                        "coordinate_id": coordinate,
                        "task": record["task_id"],
                        "framework": record["framework"],
                        "protected_class": label,
                        "public_slot": int(release["slot"]),
                        "release_slip_ns": slip,
                        "preparation_lateness_ns": max(
                            0,
                            int(release["preparation_end_ns"])
                            - int(release["release_ns"]),
                        ),
                    }
                )
    by_coordinate_class = []
    miss_counter = Counter(
        (row["coordinate_id"], int(row["protected_class"])) for row in misses
    )
    for coordinate in freeze["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        for label in (0, 1):
            slips = all_slips[(coordinate_id, label)]
            by_coordinate_class.append(
                {
                    "coordinate_id": coordinate_id,
                    "protected_class": label,
                    "deadline_miss_count": miss_counter[(coordinate_id, label)],
                    "all_release_slip_ns": {
                        "count": len(slips),
                        "p50": float(np.quantile(slips, 0.50)),
                        "p95": float(np.quantile(slips, 0.95)),
                        "p99": float(np.quantile(slips, 0.99)),
                        "max": max(slips),
                    },
                }
            )
    if len(misses) != 13:
        raise RuntimeError(f"expected 13 immutable deadline misses, found {len(misses)}")
    return {
        "role": "PRIVATE_DEVELOPMENT_DIAGNOSTIC_ONLY",
        "entered_attacker_features": False,
        "total_deadline_misses": len(misses),
        "deadline_miss_slip_ns": _percentiles(
            [int(row["release_slip_ns"]) for row in misses]
        ),
        "count_by_coordinate_and_class": by_coordinate_class,
        "affected_public_slots": misses,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite attribution output: {args.output}")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_SMOKE, head],
        cwd=ROOT,
        check=False,
    ).returncode:
        raise RuntimeError("attribution source does not descend from the immutable smoke")
    records, dataset = _load_archive_records(args.evidence_root)
    freeze = json.loads(
        (args.evidence_root / "collection/frozen_manifest.json").read_text(encoding="utf-8")
    )
    analysis_input_path = args.evidence_root / "analysis_freeze/analysis_input_manifest.json"
    analysis_input = json.loads(analysis_input_path.read_text(encoding="utf-8"))
    original = json.loads(
        (args.evidence_root / "analysis/duplex_repair_smoke_analysis.json").read_text(
            encoding="utf-8"
        )
    )
    if analysis_input["dataset_inventory_sha256"] != dataset["dataset_inventory_sha256"]:
        raise RuntimeError("selected-block input does not match the immutable dataset")
    args.output.mkdir(parents=True)
    results = _relay_analysis(records, freeze, analysis_input, original)
    slots = _slot_medians(records, analysis_input)
    private = (
        _private_deadline_diagnostics(records, freeze, args.raw_root)
        if args.raw_root is not None
        else None
    )
    report = {
        "schema": "AgentTool.V12V4R7ResidualTimingSourceAttribution/1",
        "phase": "V12-V4R7-RESIDUAL-TIMING-SOURCE-ATTRIBUTION",
        "base_smoke": BASE_SMOKE,
        "analysis_source_commit": head,
        "status": "POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC",
        "new_sessions": 0,
        "runtime_changes": 0,
        "auc_based_privacy_claims": 0,
        "dataset_identity_count": 640,
        "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        "analysis_input_manifest_sha256": sha256(analysis_input_path),
        "selected_train_blocks": 30,
        "selected_eval_blocks": 30,
        "feature_family_contract": feature_family_contract(
            freeze["feature_contract"]["RELAY_raw_widths"]
        ),
        "feature_family_results": results,
        "slot_level_medians": {
            "scope": "RESIDUAL_COMPARISONS_SELECTED_EVAL_BLOCKS_ONLY",
            "rows": len(slots),
            "file": "slot_level_boundary_medians.csv",
        },
        "private_deadline_diagnostics": private,
    }
    write_json(args.output / "attribution_analysis.json", report)
    with (args.output / "feature_family_results.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    with (args.output / "slot_level_boundary_medians.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(slots[0]))
        writer.writeheader()
        writer.writerows(slots)
    if private is not None:
        with (args.output / "deadline_miss_events.csv").open(
            "x", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(private["affected_public_slots"][0])
            )
            writer.writeheader()
            writer.writerows(private["affected_public_slots"])
    print(json.dumps({"feature_family_rows": len(results), "slot_rows": len(slots), "deadline_misses": None if private is None else private["total_deadline_misses"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
