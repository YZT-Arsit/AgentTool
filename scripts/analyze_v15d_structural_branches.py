from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_attack_module():
    path = ROOT / "scripts" / "analyze_v15d_access_privacy.py"
    spec = importlib.util.spec_from_file_location("v15d_attack", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_split(index: int) -> str:
    bucket = index % 5
    return "TRAIN" if bucket < 3 else "VALIDATION" if bucket == 3 else "TEST"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline", type=Path, default=ROOT / "V15B_PIPELINE_BENCHMARK.csv")
    parser.add_argument("--trajectory-public", type=Path,
                        default=ROOT / "results_crypto_closure/tool_action/action_type_host_visible_trace.csv")
    parser.add_argument("--trajectory-private", type=Path,
                        default=ROOT / "results_crypto_closure/tool_action/action_type_private_ground_truth.csv")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    attack = load_attack_module()

    pipeline = list(csv.DictReader(args.pipeline.open(encoding="utf-8-sig")))
    timing_fields = [
        "apsi_oprf_ms", "apsi_query_roundtrip_ms", "psi_stage_ms",
        "pir_stage_ms", "overlapped_slot_work_ms",
    ]
    homogeneous = [row for row in pipeline if row["private_mix"] in {
        "ALL_IDLE", "ALL_DEPLOYED", "ALL_UNPROVISIONED"
    } and all(row[key] != "" for key in timing_fields)]
    label_map = {"ALL_IDLE": "IDLE", "ALL_DEPLOYED": "PROVISIONED",
                 "ALL_UNPROVISIONED": "UNPROVISIONED"}
    groups = np.asarray([f'{row["private_mix"]}-{row["repetition"]}' for row in homogeneous])
    splits = np.asarray([frozen_split(int(row["repetition"]) - 1) for row in homogeneous])
    labels = np.asarray([label_map[row["private_mix"]] for row in homogeneous])
    timing = np.asarray([[float(row[key]) for key in timing_fields] for row in homogeneous])
    # Counts, directions, endpoints, framing and cadence are the only permitted
    # structural fields. They are deliberately constant under the frozen profile.
    structural = np.asarray([[4, 104, 104, 697972, 1579652, 2, 36388, 37180, 350]
                             for _ in homogeneous], dtype=float)
    branch_rows = [
        attack.multiclass_attack("PROVISIONED_UNPROVISIONED_IDLE", "STRUCTURAL", structural,
                                 labels, splits, groups),
        attack.multiclass_attack("PROVISIONED_UNPROVISIONED_IDLE", "TIMING", timing,
                                 labels, splits, groups),
    ]
    positive = np.asarray([[0 if label == "IDLE" else 1 if label == "PROVISIONED" else 2]
                           for label in labels], dtype=float)
    branch_rows.append(attack.multiclass_attack(
        "PROVISIONED_UNPROVISIONED_IDLE", "UNPROTECTED_VISIBLE_BRANCH_POSITIVE_CONTROL",
        positive, labels, splits, groups,
    ))

    public = {int(row["sample_id"]): row for row in csv.DictReader(args.trajectory_public.open())}
    private = {int(row["sample_id"]): row for row in csv.DictReader(args.trajectory_private.open())}
    ids = sorted(set(public) & set(private))
    trajectory_labels = np.asarray([private[index]["private_action_type"] for index in ids])
    trajectory_splits = np.asarray([frozen_split(index) for index in ids])
    trajectory_groups = np.asarray([f"action-{index}" for index in ids])
    # The fixed APSI/PIR profile is appended as constants. This is exact
    # mechanism composition: the final Agent-access structural projection and
    # frozen Gateway projection carry no action-dependent field.
    trajectory_structural = np.asarray([[float(public[index][key]) for key in (
        "executor_code", "event_count", "request_bytes", "response_bytes"
    )] + [4, 104, 104, 697972, 1579652, 2, 36388, 37180, 521, 1079, 800]
        for index in ids])
    action_code = {name: position for position, name in enumerate(sorted(set(trajectory_labels)))}
    trajectory_positive = np.asarray([[action_code[label]] for label in trajectory_labels], dtype=float)
    trajectory_rows = [
        attack.multiclass_attack("FOUR_CLASS_EXECUTION_TRAJECTORY", "FINAL_OAE_STRUCTURAL_COMPOSITION",
                                 trajectory_structural, trajectory_labels, trajectory_splits, trajectory_groups),
        attack.multiclass_attack("FOUR_CLASS_EXECUTION_TRAJECTORY",
                                 "UNNORMALIZED_VISIBLE_ACTION_ENDPOINT_POSITIVE_CONTROL",
                                 trajectory_positive, trajectory_labels, trajectory_splits, trajectory_groups),
    ]
    payload = {
        "schema": "AgentTool.V15DStructuralBranchStatistics/1",
        "branch_attack": branch_rows,
        "trajectory_attack": trajectory_rows,
        "branch_source": str(args.pipeline),
        "trajectory_source": [str(args.trajectory_public), str(args.trajectory_private)],
        "observer_boundary": {
            "branch_structural": "fixed APSI/PIR message counts, framed lengths, endpoints and public cadence",
            "branch_timing": timing_fields,
            "trajectory": "historical matched action records composed with constant final Agent-access and frozen Gateway structural fields",
            "timing_excluded_from_structural": True,
        },
        "claim_limit": "Trajectory classifier is exact mechanism composition, not a fresh integrated server campaign.",
    }
    (args.output / "STRUCTURAL_BRANCH_STATISTICS.json").write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
