from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from dataclasses import replace

from v11_full_scope.fixtures import tool_case
from v11_full_scope.frameworks import run_framework_case
from v11_online.session import OnlineSimplePIRResolver, _PendingPIRResolution
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import TimingIndistinguishabilityProfile, candidate_profiles
from v12_timing.projection import (
    registry_timing_projection,
    relay_timing_projection,
    timing_feature_vector,
)


def _relay_event(round_number: int, request_ns: int, response_ns: int) -> dict[str, object]:
    return {
        "profile_id": "V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        "session": 1,
        "round": round_number,
        "request_length": 1079,
        "response_length": 800,
        "relay_endpoint": "LOCAL_RELAY",
        "gateway_endpoint": "LOCAL_GATEWAY",
        "request_observed_ns": request_ns,
        "response_observed_ns": response_ns,
        "client_http_version": "HTTP/2.0",
        "gateway_http_version": "HTTP/2.0",
        "operation_id": "must-not-survive",
    }


def test_timing_profile_candidates_are_distinct_and_predeclared() -> None:
    profiles = candidate_profiles()
    assert len(profiles) == 9
    assert {profile.round_period_ms for profile in profiles} == {10, 20, 25}
    assert {profile.pir_resolution_period_ms for profile in profiles} == {60, 75, 100}
    assert all(profile.profile_class == "TIMING_INDISTINGUISHABILITY_PROFILE" for profile in profiles)
    assert all(profile.public_session_liveness_cap_ms == 60_000 for profile in profiles)
    assert all(profile.pir_initial_lead_ms == 25 for profile in profiles)
    assert all(not profile.profile_id.startswith("V11_4-") for profile in profiles)


def test_relay_attack_projection_rejects_private_fields() -> None:
    events = [_relay_event(1, 1_000, 1_300), _relay_event(2, 2_000, 2_400)]
    projection = relay_timing_projection({"public_relay_events": events})
    assert projection["authenticated_slot_order"] == [1, 2]
    assert projection["request_inter_arrival_ns"] == [1_000]
    assert "operation_id" not in str(projection)
    assert len(timing_feature_vector(projection)) > 0


def test_registry_attack_projection_has_only_modeled_metadata() -> None:
    rows = [
        {
            "ordinal": ordinal,
            "query_bytes": 4096,
            "query_rows": 8,
            "query_cols": 8,
            "answer_bytes": 2048,
            "executor": "SimplePIRServer",
            "request_kind": "ONLINE_PIR_QUERY",
            "request_arrival_ns": 10_000 + ordinal * 60_000_000,
            "answer_ready_ns": 20_000 + ordinal * 60_000_000,
        }
        for ordinal in range(3)
    ]
    projection = registry_timing_projection(
        rows,
        profile_id="V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        pir_period_ms=60,
        opportunities=3,
    )
    assert projection["ordinals"] == [0, 1, 2]
    assert projection["inter_query_gap_ns"] == [60_000_000, 60_000_000]
    assert "private_index" not in str(projection)
    assert len(timing_feature_vector(projection)) > 0


def test_dummy_descriptor_cannot_grant_real_capability() -> None:
    descriptor = OnlineSimplePIRResolver._dummy_descriptor(999)
    assert descriptor.agent_service is None
    assert descriptor.allowed_tool_capabilities == ()
    assert descriptor.capability_ids == ("agent.cover.noop",)
    assert descriptor.trust_class == "AUTHENTICATED_COVER_NOOP"


def test_fixed_pir_scheduler_uses_one_protocol_function_for_real_and_dummy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolver = OnlineSimplePIRResolver(tmp_path, record_count=1000)
    resolver.cover_opportunities = 3
    resolver.cover_period_ms = 60
    resolver.cover_initial_lead_ms = 25
    resolver.cover_liveness_cap_ms = 60_000
    pending = _PendingPIRResolution("real-operation", 10)
    resolver.cover_pending.append(pending)
    calls: list[tuple[str, int]] = []

    def execute(operation_id: str, index: int):
        calls.append((operation_id, index))
        return resolver._dummy_descriptor(index) if index == 999 else object()

    ticks = iter(range(0, 10_000_000_000, 60_000_000))
    monkeypatch.setattr("v11_online.session.time.monotonic_ns", lambda: next(ticks))
    monkeypatch.setattr("v11_online.session.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(resolver, "_execute_query", execute)
    resolver._run_cover_schedule()

    assert calls[0] == ("real-operation", 10)
    assert [index for _, index in calls[1:]] == [999, 999]
    assert resolver.real_query_count == 1
    assert resolver.dummy_query_count == 2
    assert pending.ready.is_set()
    assert resolver.cover_complete


def test_pir_query_has_no_direct_process_write_outside_protocol_executor() -> None:
    query_source = inspect.getsource(OnlineSimplePIRResolver.query)
    executor_source = inspect.getsource(OnlineSimplePIRResolver._execute_query)
    assert ".stdin.write" not in query_source
    assert ".stdin.write" in executor_source


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "common_action_gateway_v2" / "bin" / "canonical-v12-timing-runner").is_file(), reason="Linux timing development binary unavailable")
def test_actual_timing_profile_emits_full_transcript_and_fixed_pir_schedule(tmp_path: Path) -> None:
    case = replace(
        tool_case("DEV-V12-TIMING-COMPONENT-001", "OpenAI Agents SDK"),
        capability="tool.read",
    )
    profile = TimingIndistinguishabilityProfile(
        profile_id="V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        round_period_ms=10,
        pir_resolution_period_ms=60,
    ).validate()
    with CanonicalOnlineSession(tmp_path / "canonical", [case], public_profile=profile) as session:
        canonical = run_framework_case(case, session.implementation())
    assert canonical.operation_outcome_semantics == "READ_ONLY:SUCCESS"
    assert session.trace is not None
    assert session.trace["session_status"] == "COMPLETE"
    assert session.trace["public_transcript_complete"]
    assert session.trace["emitted_cells"] == profile.total_rounds
    assert len(session.trace["public_relay_events"]) == profile.total_rounds
    summary = (tmp_path / "canonical" / "pir" / "online_query_summary.json").read_text(encoding="utf-8")
    assert '"query_count": 50' in summary
    assert '"real_query_count": 1' in summary
    assert '"dummy_query_count": 49' in summary
