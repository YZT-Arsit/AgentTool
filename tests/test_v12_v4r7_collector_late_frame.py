from __future__ import annotations

from copy import deepcopy

from v12_timing.collector_integrity import v4r7_public_transcript_contract
from v12_timing.projection import expected_raw_timing_widths

R = 521
Q = 100
PERIOD_NS = 10_000_000


def _fixture(*, deadline_misses: int = 2):
    releases = []
    relay = []
    previous_actual = 0
    for slot in range(1, R + 1):
        release = previous_actual + PERIOD_NS
        slip = 1_000_000 if slot <= deadline_misses else 100_000
        actual = release + slip
        releases.append(
            {
                "slot": slot,
                "release_ns": release,
                "actual_release_ns": actual,
                "release_slip_ns": slip,
                "deadline_miss": slot <= deadline_misses,
                "release_attempted": True,
                "response_write_completed": True,
            }
        )
        relay.append(
            {
                "round": slot,
                "request_length": 1079,
                "response_length": 800,
                "client_to_relay_receive_ns": slot,
                "relay_to_gateway_send_ns": slot + 1,
                "gateway_to_relay_receive_ns": slot + 2,
                "relay_to_client_send_ns": slot + 3,
            }
        )
        previous_actual = actual
    registry = [
        {
            "ordinal": ordinal,
            "query_bytes": 2020,
            "answer_bytes": 6592,
            "request_arrival_ns": ordinal + 1,
            "response_send_ns": ordinal + 2,
        }
        for ordinal in range(Q)
    ]
    cover = [{"ordinal": ordinal} for ordinal in range(Q)]
    trace = {
        "session_status": "COMPLETE",
        "public_transcript_complete": True,
        "response_release_opportunities": R,
        "response_release_attempts": R,
        "successful_response_writes": R,
        "relay_application_received_cells": R,
        "public_relay_events": relay,
        "gateway_response_releases": releases,
        "infrastructure_liveness_failure": False,
    }
    return trace, registry, cover


def _checks(trace, registry, cover):
    return v4r7_public_transcript_contract(
        trace,
        registry,
        cover,
        expected_rounds=R,
        expected_queries=Q,
        response_period_ms=10,
        expected_request_bytes=1079,
        expected_response_bytes=800,
    )


def test_two_allowed_deadline_slips_remain_complete() -> None:
    checks, diagnostics = _checks(*_fixture(deadline_misses=2))
    assert all(checks.values())
    assert diagnostics["response_deadline_miss_count"] == 2
    assert diagnostics["deadline_slip_is_integrity_failure"] is False


def test_many_allowed_deadline_slips_remain_complete() -> None:
    checks, diagnostics = _checks(*_fixture(deadline_misses=R))
    assert all(checks.values())
    assert diagnostics["response_deadline_miss_count"] == R


def test_missing_and_duplicate_slots_fail_closed() -> None:
    trace, registry, cover = _fixture()
    trace["public_relay_events"].pop()
    checks, _ = _checks(trace, registry, cover)
    assert not checks["relay_event_count_exact"]
    assert not checks["relay_slot_set_exact"]

    trace, registry, cover = _fixture()
    trace["public_relay_events"][-1]["round"] = R - 1
    checks, _ = _checks(trace, registry, cover)
    assert not checks["relay_slot_set_exact"]
    assert not checks["relay_slot_ids_unique"]


def test_failed_write_and_inconsistent_transcript_fail_closed() -> None:
    trace, registry, cover = _fixture()
    trace["gateway_response_releases"][100]["response_write_completed"] = False
    trace["successful_response_writes"] = R - 1
    checks, _ = _checks(trace, registry, cover)
    assert not checks["every_response_write_completed"]
    assert not checks["successful_response_writes_exact"]

    trace, registry, cover = _fixture()
    trace["relay_application_received_cells"] = R - 1
    trace["public_relay_events"].pop()
    checks, _ = _checks(trace, registry, cover)
    assert trace["public_transcript_complete"] is True
    assert not checks["relay_application_receipts_exact"]
    assert not checks["relay_event_count_exact"]


def test_actual_response_catch_up_violation_fails_closed() -> None:
    trace, registry, cover = _fixture()
    previous = trace["gateway_response_releases"][10]
    current = trace["gateway_response_releases"][11]
    current["release_ns"] = previous["actual_release_ns"] + PERIOD_NS - 1
    checks, _ = _checks(trace, registry, cover)
    assert not checks["response_no_catch_up_contract"]


def test_collector_repair_does_not_change_feature_width_or_fields() -> None:
    before = expected_raw_timing_widths(
        "RELAY", public_r=R, public_q=Q, has_relay_duplex=True
    )
    trace, registry, cover = deepcopy(_fixture())
    checks, diagnostics = _checks(trace, registry, cover)
    after = expected_raw_timing_widths(
        "RELAY", public_r=R, public_q=Q, has_relay_duplex=True
    )
    assert all(checks.values())
    assert before == after == (521, 520, 521, 520, 521, 520, 521, 520, 521, 521, 521)
    assert set(diagnostics) == {
        "response_deadline_miss_count",
        "response_release_slip_ns",
        "maximum_response_release_slip_ns",
        "deadline_slip_is_integrity_failure",
    }
