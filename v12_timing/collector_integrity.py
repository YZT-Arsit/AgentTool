from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any


def v4r7_public_transcript_contract(
    trace: Mapping[str, Any],
    registry_rows: Sequence[Mapping[str, Any]],
    cover_rows: Sequence[Mapping[str, Any]],
    *,
    expected_rounds: int,
    expected_queries: int,
    response_period_ms: int,
    expected_request_bytes: int,
    expected_response_bytes: int,
) -> tuple[dict[str, bool], dict[str, Any]]:
    """Evaluate the V4R7 public transcript without treating release slip as loss."""
    relay_events = list(trace.get("public_relay_events", []))
    releases = list(trace.get("gateway_response_releases", []))
    expected_slots = list(range(1, expected_rounds + 1))
    relay_slots = [int(row.get("round", -1)) for row in relay_events]
    release_slots = [int(row.get("slot", -1)) for row in releases]
    registry_ordinals = [int(row.get("ordinal", -1)) for row in registry_rows]
    period_ns = response_period_ms * 1_000_000

    no_catch_up = len(releases) == expected_rounds
    for previous, current in pairwise(releases):
        previous_actual = int(previous.get("actual_release_ns", -1))
        current_deadline = int(current.get("release_ns", -1))
        if previous_actual < 0 or current_deadline < previous_actual + period_ns:
            no_catch_up = False
            break

    registry_shape = {
        (int(row.get("query_bytes", -1)), int(row.get("answer_bytes", -1)))
        for row in registry_rows
    }
    checks = {
        "runtime_session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "response_release_opportunities_exact": int(
            trace.get("response_release_opportunities", -1)
        )
        == expected_rounds,
        "response_release_attempts_exact": int(
            trace.get("response_release_attempts", -1)
        )
        == expected_rounds,
        "successful_response_writes_exact": int(
            trace.get("successful_response_writes", -1)
        )
        == expected_rounds,
        "relay_application_receipts_exact": int(
            trace.get("relay_application_received_cells", -1)
        )
        == expected_rounds,
        "relay_event_count_exact": len(relay_events) == expected_rounds,
        "relay_slot_set_exact": sorted(relay_slots) == expected_slots,
        "relay_slot_ids_unique": len(set(relay_slots)) == len(relay_slots),
        "gateway_release_count_exact": len(releases) == expected_rounds,
        "gateway_release_slot_set_exact": sorted(release_slots) == expected_slots,
        "gateway_release_slot_ids_unique": len(set(release_slots)) == len(release_slots),
        "every_release_attempted": all(
            row.get("release_attempted") is True for row in releases
        ),
        "every_response_write_completed": all(
            row.get("response_write_completed") is True for row in releases
        ),
        "no_response_write_error": all(
            not str(row.get("response_write_error", "")) for row in releases
        ),
        "fixed_request_size": all(
            int(row.get("request_length", -1)) == expected_request_bytes
            for row in relay_events
        ),
        "fixed_response_size": all(
            int(row.get("response_length", -1)) == expected_response_bytes
            for row in relay_events
        ),
        "complete_duplex_relay_boundaries": all(
            all(
                int(row.get(field, 0)) > 0
                for field in (
                    "client_to_relay_receive_ns",
                    "relay_to_gateway_send_ns",
                    "gateway_to_relay_receive_ns",
                    "relay_to_client_send_ns",
                )
            )
            for row in relay_events
        ),
        "response_no_catch_up_contract": no_catch_up,
        "registry_count_exact": len(registry_rows) == expected_queries,
        "registry_ordinal_set_exact": sorted(registry_ordinals)
        == list(range(expected_queries)),
        "registry_ordinals_unique": len(set(registry_ordinals))
        == len(registry_ordinals),
        "registry_fixed_public_shape": len(registry_shape) == 1
        and next(iter(registry_shape), (-1, -1))[0] > 0
        and next(iter(registry_shape), (-1, -1))[1] > 0,
        "registry_application_timestamps_complete": all(
            int(row.get("request_arrival_ns", 0)) > 0
            and int(row.get("response_send_ns", 0)) > 0
            for row in registry_rows
        ),
        "cover_schedule_exact": len(cover_rows) == expected_queries
        and all(
            int(row.get("ordinal", -1)) == index
            for index, row in enumerate(cover_rows)
        ),
        "no_infrastructure_liveness_failure": trace.get(
            "infrastructure_liveness_failure"
        )
        is False,
    }
    slips = [int(row.get("release_slip_ns", 0)) for row in releases]
    diagnostics = {
        "response_deadline_miss_count": sum(
            bool(row.get("deadline_miss")) for row in releases
        ),
        "response_release_slip_ns": slips,
        "maximum_response_release_slip_ns": max(slips, default=0),
        "deadline_slip_is_integrity_failure": False,
    }
    return checks, diagnostics
