from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from v12_timing.projection import (
    expected_raw_timing_widths,
    relay_timing_projection,
    timing_feature_vector,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _structure(events: list[dict[str, Any]], expected_rounds: int) -> dict[str, Any]:
    slots = [int(event["round"]) for event in events]
    counts = Counter(slots)
    required = set(range(1, expected_rounds + 1))
    chronological = sorted(
        events, key=lambda event: (int(event["request_observed_ns"]), int(event["round"]))
    )
    arrival_slots = [int(event["round"]) for event in chronological]
    arrival_rank = {slot: rank for rank, slot in enumerate(arrival_slots, 1)}
    reordered_pairs = [
        {
            "earlier_arrival_slot": arrival_slots[index],
            "later_arrival_slot": arrival_slots[index + 1],
            "earlier_request_observed_ns": int(chronological[index]["request_observed_ns"]),
            "later_request_observed_ns": int(chronological[index + 1]["request_observed_ns"]),
        }
        for index in range(len(chronological) - 1)
        if arrival_slots[index] > arrival_slots[index + 1]
    ]
    return {
        "event_count": len(events),
        "exact_R_events": len(events) == expected_rounds,
        "slot_set_complete": set(slots) == required,
        "duplicate_slots": sorted(slot for slot, count in counts.items() if count > 1),
        "missing_slots": sorted(required - set(slots)),
        "wrong_slot_ids": sorted(set(slots) - required),
        "arrival_reordered": arrival_slots != list(range(1, expected_rounds + 1)),
        "maximum_reorder_displacement": max(
            (abs(arrival_rank.get(slot, slot) - slot) for slot in required), default=0
        ),
        "reordered_adjacent_arrival_pairs": reordered_pairs,
        "response_send_complete": all("response_send_ns" in event for event in events),
        "request_response_slot_pairing_valid": all(
            int(event.get("response_send_ns", -1)) >= int(event["request_observed_ns"])
            for event in events
        ),
        "request_sizes": sorted({int(event["request_length"]) for event in events}),
        "response_sizes": sorted({int(event["response_length"]) for event in events}),
        "session_ids": sorted({int(event["session"]) for event in events}),
        "profile_ids": sorted({str(event["profile_id"]) for event in events}),
    }


def audit(campaign_root: Path, *, original_abort_identity: str, expected_rounds: int,
          expected_request_bytes: int, expected_response_bytes: int) -> dict[str, Any]:
    manifest_path = campaign_root / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    complete_records = [
        record for record in manifest["session_records"] if record["status"] == "COMPLETE"
    ]
    aggregate = {
        "total_sessions_audited": 0,
        "exact_R_events_present": 0,
        "slot_set_exactly_1_through_R": 0,
        "sessions_with_duplicate_slots": 0,
        "sessions_with_missing_slots": 0,
        "sessions_with_wrong_slot_ids": 0,
        "sessions_with_application_arrival_reordering": 0,
        "maximum_reorder_displacement": 0,
        "request_response_slot_pairing_valid": 0,
        "corrected_projection_pass": 0,
        "corrected_projection_fail": 0,
        "corrected_feature_width_consistent": 0,
    }
    projection_failures: list[dict[str, str]] = []
    expected_widths = expected_raw_timing_widths(
        "RELAY", public_r=expected_rounds, public_q=100, has_relay_send=True
    )
    expected_feature_width = sum(expected_widths) + 12 * len(expected_widths) + 1
    for record in complete_records:
        # Intentionally do not read label, task, framework, partition, pair, or observer projections.
        record_path = campaign_root / record["path"]
        raw_path = record_path.parent / "go_online_result.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        events = raw["public_relay_events"]
        structure = _structure(events, expected_rounds)
        aggregate["total_sessions_audited"] += 1
        aggregate["exact_R_events_present"] += int(structure["exact_R_events"])
        aggregate["slot_set_exactly_1_through_R"] += int(structure["slot_set_complete"])
        aggregate["sessions_with_duplicate_slots"] += int(bool(structure["duplicate_slots"]))
        aggregate["sessions_with_missing_slots"] += int(bool(structure["missing_slots"]))
        aggregate["sessions_with_wrong_slot_ids"] += int(bool(structure["wrong_slot_ids"]))
        aggregate["sessions_with_application_arrival_reordering"] += int(
            structure["arrival_reordered"]
        )
        aggregate["maximum_reorder_displacement"] = max(
            aggregate["maximum_reorder_displacement"],
            structure["maximum_reorder_displacement"],
        )
        aggregate["request_response_slot_pairing_valid"] += int(
            structure["request_response_slot_pairing_valid"]
        )
        try:
            projection = relay_timing_projection(
                raw, expected_rounds=expected_rounds,
                require_complete_application_timing=True,
                expected_request_bytes=expected_request_bytes,
                expected_response_bytes=expected_response_bytes,
            )
            vector = timing_feature_vector(projection, raw_widths=expected_widths)
            aggregate["corrected_projection_pass"] += 1
            aggregate["corrected_feature_width_consistent"] += int(
                len(vector) == expected_feature_width
            )
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            aggregate["corrected_projection_fail"] += 1
            projection_failures.append({
                "execution_record_path": record["path"],
                "exception": f"{type(exc).__name__}: {exc}",
            })

    abort_record = next(
        record for record in manifest["session_records"]
        if record["identity"] == original_abort_identity
    )
    abort_record_path = campaign_root / abort_record["path"]
    abort_raw_path = abort_record_path.parent / "go_online_result.json"
    abort_raw = json.loads(abort_raw_path.read_text(encoding="utf-8"))
    abort_events = abort_raw["public_relay_events"]
    abort_structure = _structure(abort_events, expected_rounds)
    abort_projection_status = "PASS"
    abort_feature_width = None
    try:
        abort_projection = relay_timing_projection(
            abort_raw, expected_rounds=expected_rounds,
            require_complete_application_timing=True,
            expected_request_bytes=expected_request_bytes,
            expected_response_bytes=expected_response_bytes,
        )
        abort_feature_width = len(timing_feature_vector(abort_projection, raw_widths=expected_widths))
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        abort_projection_status = f"FAIL: {type(exc).__name__}: {exc}"
    abort_structure.update({
        "identity": original_abort_identity,
        "raw_path": str(abort_raw_path),
        "raw_sha256": _sha256(abort_raw_path),
        "corrected_projection": abort_projection_status,
        "corrected_feature_width": abort_feature_width,
        "public_transcript_complete": abort_raw.get("public_transcript_complete"),
        "session_status": abort_raw.get("session_status"),
        "infrastructure_liveness_failure": abort_raw.get("infrastructure_liveness_failure"),
        "profile_overflow_events": abort_raw.get("profile_overflow_events"),
        "silent_committed_result_losses": abort_raw.get("silent_committed_result_losses"),
        "pending_operation_ids": abort_raw.get("pending_operation_ids"),
    })
    return {
        "schema": "AgentTool.V12RelayProjectionOrderingStructuralAudit/1",
        "methodology_only": True,
        "protected_labels_accessed": False,
        "class_conditioning_performed": False,
        "classifier_training_runs": 0,
        "auc_calculations": 0,
        "bootstrap_runs_on_protected_data": 0,
        "campaign_manifest": str(manifest_path),
        "campaign_manifest_sha256": _sha256(manifest_path),
        "expected_public_R": expected_rounds,
        "expected_raw_widths": list(expected_widths),
        "expected_feature_width": expected_feature_width,
        "complete_session_aggregate": aggregate,
        "projection_failures": projection_failures,
        "original_abort_session": abort_structure,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_root", type=Path)
    parser.add_argument("--original-abort-identity", required=True)
    parser.add_argument("--expected-rounds", type=int, required=True)
    parser.add_argument("--expected-request-bytes", type=int, required=True)
    parser.add_argument("--expected-response-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.campaign_root,
        original_abort_identity=args.original_abort_identity,
        expected_rounds=args.expected_rounds,
        expected_request_bytes=args.expected_request_bytes,
        expected_response_bytes=args.expected_response_bytes,
    )
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
