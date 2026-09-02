from __future__ import annotations

import json
from pathlib import Path

import pytest

from v12_timing.projection import (
    TIMING_ONLY_VIEW,
    expected_raw_timing_widths,
    relay_timing_projection,
    timing_feature_vector,
)

ROOT = Path(__file__).resolve().parents[1]


def _rows() -> list[dict[str, object]]:
    rows = []
    for slot in range(1, 13):
        request = 1_000_000 + slot * 1_000
        rows.append({
            "profile_id": "P10", "session": 1, "round": slot,
            "request_length": 1079, "response_length": 800,
            "request_observed_ns": request,
            "response_send_ns": request + 300 + slot,
            "operation_id": f"private-{slot}",
            "new_private_field": {"secret": slot},
        })
    # Public slot 11 reaches the application before slot 10.
    rows[9]["request_observed_ns"] = 1_011_500
    rows[10]["request_observed_ns"] = 1_010_500
    rows[9]["response_send_ns"] = 1_011_900
    rows[10]["response_send_ns"] = 1_010_900
    return rows


def _project(rows: list[dict[str, object]]) -> dict[str, object]:
    return relay_timing_projection(
        {"public_relay_events": rows}, expected_rounds=12,
        require_complete_application_timing=True,
        expected_request_bytes=1079, expected_response_bytes=800,
    )


def test_complete_slot_set_is_accepted_despite_timestamp_reordering() -> None:
    projection = _project(_rows())
    assert projection["view"] == TIMING_ONLY_VIEW
    assert projection["public_slot_order"] == list(range(1, 13))


@pytest.mark.parametrize(
    "mutate",
    (
        lambda rows: rows.__setitem__(10, dict(rows[10], round=10)),
        lambda rows: rows.pop(10),
        lambda rows: rows.__setitem__(10, dict(rows[10], round=13)),
    ),
)
def test_duplicate_missing_and_wrong_slot_ids_are_rejected(mutate) -> None:
    rows = _rows()
    mutate(rows)
    with pytest.raises(ValueError, match="public R|complete unique"):
        _project(rows)


def test_slot_indexing_preserves_inversion_and_response_pairing() -> None:
    rows = _rows()
    projection = _project(rows)
    request = projection["slot_indexed_session_relative_request_ns"]
    response = projection["slot_indexed_session_relative_response_send_ns"]
    paired = projection["slot_paired_request_response_ns"]
    assert request[9] > request[10]
    assert response[9] > response[10]
    assert paired[9] == rows[9]["response_send_ns"] - rows[9]["request_observed_ns"]
    assert paired[10] == rows[10]["response_send_ns"] - rows[10]["request_observed_ns"]
    assert all(value >= 0 for value in projection["chronological_request_inter_arrival_ns"])
    assert all(value >= 0 for value in projection["chronological_response_send_inter_arrival_ns"])


def test_raw_feature_width_is_public_and_private_fields_cannot_enter() -> None:
    projection = _project(_rows())
    widths = expected_raw_timing_widths(
        "RELAY", public_r=12, public_q=100, has_relay_send=True,
    )
    assert widths == (12, 11, 12, 11, 12)
    vector = timing_feature_vector(projection, raw_widths=widths)
    assert len(vector) == sum(widths) + 12 * len(widths) + 1
    assert "private" not in repr(projection)
    assert "secret" not in repr(projection)


def test_strictly_ordered_historical_trace_remains_valid() -> None:
    rows = _rows()
    rows[9]["request_observed_ns"] = 1_010_000
    rows[10]["request_observed_ns"] = 1_011_000
    rows[9]["response_send_ns"] = 1_010_400
    rows[10]["response_send_ns"] = 1_011_400
    projection = _project(rows)
    assert projection["slot_indexed_session_relative_request_ns"] == sorted(
        projection["slot_indexed_session_relative_request_ns"]
    )


def test_fixed_public_sizes_are_enforced() -> None:
    rows = _rows()
    rows[4]["request_length"] = 1080
    with pytest.raises(ValueError, match="fixed|public profile"):
        _project(rows)


def test_registry_strict_order_has_a_single_sequential_request_response_path() -> None:
    session = (ROOT / "v11_online/session.py").read_text(encoding="utf-8")
    bridge = (ROOT / "pir_integration/simplepir_bridge/main.go").read_text(encoding="utf-8")
    query_lock = session.index("with self.query_lock:")
    request_write = session.index("self.process.stdin.write", query_lock)
    execute_start = session.index("def _execute_query")
    execute_end = session.index("def ", execute_start + 4)
    execute_source = session[execute_start:execute_end]
    ordinal_loop = session.index("for ordinal in range(self.cover_opportunities):")
    execute = session.index("self._execute_query(operation_id, index)", ordinal_loop)
    assert query_lock < request_write
    assert "_submit_query" in execute_source
    assert "_await_response" in execute_source
    assert ordinal_loop < execute
    bridge_loop = bridge.index("for reader.Scan()")
    prepare = bridge.index("preparationJobs <- job", bridge_loop)
    enqueue = bridge.index("releaseJobs <- job", prepare)
    release_loop = bridge.index("for job := range releaseJobs", enqueue)
    prepared = bridge.index("prepared = <-job.prepared", release_loop)
    arrival = bridge.index("arrivalNS := time.Now().UnixNano()", prepared)
    response_loop = bridge.index("for job := range responseJobs", arrival)
    emit = bridge.index("emitInteractiveResponse(encoder, completed.response)", response_loop)
    assert bridge_loop < prepare < enqueue < release_loop < prepared < arrival < response_loop < emit


def test_statistical_protocol_v3_only_revises_relay_projection_semantics() -> None:
    protocol = json.loads((ROOT / "V12_TIMING_STATISTICAL_PROTOCOL_V3.json").read_text())
    assert protocol["status"] == "PASS"
    assert protocol["supersedes_commit"] == "3dde92221b274148f4926de4d4df07d8a6c64cd5"
    assert protocol["relay_integrity_contract"]["chronological_slot_equality_required"] is False
    preserved = protocol["unchanged_statistical_protocol"]
    assert preserved["train_only_model_selection"] is True
    assert preserved["train_only_score_orientation"] is True
    assert preserved["bootstrap_resamples"] == 10_000
    assert preserved["protected_rule"] == "UCB95 <= 0.55"
    assert preserved["sentinel_rule"] == (
        "ANY observer comparison LCB99.5 > 0.55 means EARLY_FAIL"
    )
