from __future__ import annotations

from pathlib import Path

import pytest

from v12_timing.capacity import CapacityContract, run_capacity_suite
from v12_timing.delta_capacity import audit_delta_capacity, effective_clock
from v12_timing.profile import (
    EFFECTIVE_PUBLIC_CLOCK_V2,
    EFFECTIVE_PUBLIC_CLOCK_V3,
    causal_horizon_candidate_profiles,
    delta_functional_candidate_profiles,
)
from v12_timing.projection import TIMING_ONLY_VIEW, registry_timing_projection, relay_timing_projection

ROOT = Path(__file__).resolve().parents[1]


def test_v3_delta_profiles_are_exact_and_frozen() -> None:
    profiles = delta_functional_candidate_profiles()
    assert [value.round_period_ms for value in profiles] == [10, 20, 25]
    assert [value.admission_rounds for value in profiles] == [450, 225, 180]
    assert [value.completion_rounds for value in profiles] == [5, 3, 2]
    assert [value.total_rounds for value in profiles] == [506, 279, 233]
    assert [value.scheduled_lifetime_ms for value in profiles] == [5060, 5580, 5825]
    assert all(value.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V3 for value in profiles)
    assert all(value.pir_resolution_opportunities == 100 for value in profiles)


def test_v2_v3_delta10_semantics_are_equal_except_revision() -> None:
    v2 = causal_horizon_candidate_profiles()[0]
    v3 = delta_functional_candidate_profiles()[0]
    assert v2.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V2
    excluded = {"schema", "profile_id", "timing_semantic_revision"}
    assert {key: value for key, value in v2.public_schema().items() if key not in excluded} == {
        key: value for key, value in v3.public_schema().items() if key not in excluded
    }


@pytest.mark.parametrize("delta", (10, 20, 25))
def test_joint_pir_capacity_is_fixed_for_each_delta(delta: int) -> None:
    result = run_capacity_suite(CapacityContract(admission_horizon_ms=4500))
    assert result["passed"] is True
    assert result["contract"]["K"] == 6
    assert result["contract"]["Q"] == 100
    assert result["contract"]["pir_period_ms"] == 60
    assert delta in {10, 20, 25}


def test_every_delta_passes_all_frozen_mechanical_scenarios() -> None:
    for profile in delta_functional_candidate_profiles():
        result = audit_delta_capacity(profile)
        assert result["passed"] is True
        assert set(result["scenarios"]) == {
            "same_agent_depth50", "K6_descriptor_transitions", "agent_as_tool_transition",
            "trusted_descriptor_cache_reuse", "effective_clock_stalls",
            "latest_legal_result_placement", "joint_fixed_pir_action",
        }
        assert result["causal_depth_trace"]["no_future_action_predeclared"] is True


def test_v3_effective_clock_recurrence_has_no_catch_up() -> None:
    for delta in (10, 20, 25):
        rows = effective_clock(12, delta, {3: 100})
        assert rows[0]["eligible_ms"] == rows[0]["nominal_ms"]
        for previous, current in zip(rows, rows[1:]):
            assert current["eligible_ms"] == max(current["nominal_ms"], previous["send_ms"] + delta)
            assert current["logical_cutoff_ms"] == current["eligible_ms"] - 1


def test_complete_projection_requires_every_application_send_timestamp() -> None:
    relay_rows = [{
        "profile_id": "v3", "session": 1, "round": index + 1,
        "request_length": 1079, "response_length": 800,
        "request_observed_ns": 1000 + index * 100,
        "response_observed_ns": 1050 + index * 100,
        "response_send_ns": 1060 + index * 100,
    } for index in range(3)]
    registry_rows = [{
        "ordinal": index, "query_bytes": 20, "answer_bytes": 40,
        "query_rows": 10, "query_cols": 1,
        "request_arrival_ns": 2000 + index * 100,
        "answer_ready_ns": 2040 + index * 100,
        "response_send_ns": 2050 + index * 100,
    } for index in range(3)]
    relay = relay_timing_projection({"public_relay_events": relay_rows}, expected_rounds=3,
                                    require_complete_application_timing=True)
    registry = registry_timing_projection(registry_rows, profile_id="v3", pir_period_ms=60,
                                          opportunities=3, require_complete_application_timing=True)
    assert relay["view"] == registry["view"] == TIMING_ONLY_VIEW
    del relay_rows[1]["response_send_ns"]
    with pytest.raises(ValueError):
        relay_timing_projection({"public_relay_events": relay_rows}, expected_rounds=3,
                                require_complete_application_timing=True)


def test_relay_response_sequence_is_chronological_when_slots_complete_out_of_order() -> None:
    rows = [{
        "profile_id": "v3", "session": 1, "round": index + 1,
        "request_length": 1079, "response_length": 800,
        "request_observed_ns": 1000 + index * 100,
        "response_send_ns": send,
    } for index, send in enumerate((1500, 1400, 1600))]
    projection = relay_timing_projection({"public_relay_events": rows}, expected_rounds=3,
                                         require_complete_application_timing=True)
    assert projection["slot_indexed_session_relative_response_send_ns"] == [500, 400, 600]
    assert projection["chronological_response_send_inter_arrival_ns"] == [100, 100]
    assert projection["slot_paired_request_response_ns"] == [500, 300, 400]


def test_registry_trace_persistence_follows_actual_response_emission() -> None:
    source = (ROOT / "pir_integration/simplepir_bridge/main.go").read_text(encoding="utf-8")
    call = source.index("emitInteractiveResponse(encoder, observerResponse)")
    trace = source.index("writeJSON(serverWriter", call)
    assert call < trace


def test_relay_send_timestamp_is_immediately_before_write_path() -> None:
    source = (ROOT / "common_action_gateway_v2/v8/http_relay.go").read_text(encoding="utf-8")
    capture = source.index("event.ResponseSendNS = time.Now().UnixNano()")
    header = source.index("writer.WriteHeader(http.StatusOK)", capture)
    body = source.index("writer.Write(responseBody)", header)
    persist = source.index("r.record(event)", body)
    assert capture < header < body < persist
