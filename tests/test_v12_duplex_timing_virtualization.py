from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from v11_online.session import OnlineSimplePIRResolver, duplex_pir_opportunity_times
from v12_timing.profile import (
    DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R4,
    duplex_timing_candidate_profiles,
)
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    expected_raw_timing_widths,
    relay_timing_projection,
    timing_feature_vector,
)

ROOT = Path(__file__).resolve().parents[1]


def _duplex_rows(rounds: int = 3) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for slot in range(1, rounds + 1):
        receive = 1_000_000 + slot * 100
        gateway_send = receive + 10
        gateway_receive = gateway_send + 50
        client_send = gateway_receive + 10
        rows.append(
            {
                "profile_id": "V12-TIMING-INDIST-V4-H50-H4500-P10-PIR60",
                "session": 1,
                "round": slot,
                "request_length": 1079,
                "response_length": 800,
                "request_observed_ns": receive,
                "response_send_ns": client_send,
                "client_to_relay_receive_ns": receive,
                "relay_to_gateway_send_ns": gateway_send,
                "gateway_to_relay_receive_ns": gateway_receive,
                "relay_to_client_send_ns": client_send,
            }
        )
    return rows


def test_v4_profiles_preserve_public_dimensions() -> None:
    profiles = duplex_timing_candidate_profiles()
    assert [profile.round_period_ms for profile in profiles] == [10, 20, 25]
    assert [profile.total_rounds for profile in profiles] == [506, 279, 233]
    for profile in profiles:
        assert (
            profile.timing_semantic_revision
            == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R4
        )
        assert profile.response_preparation_lead_ms == 50
        assert profile.response_preparation_workers == 6
        assert profile.pir_commitment_lead_ms == 20
        assert profile.request_final_bytes == 1079
        assert profile.response_final_bytes == 800
        assert profile.pir_resolution_opportunities == 100
        assert profile.registry_worker_lanes == 1
        assert profile.registry_max_inflight == 100


def test_strengthened_relay_projection_is_allowlisted_and_fixed_width() -> None:
    projection = relay_timing_projection(
        {"public_relay_events": _duplex_rows()},
        expected_rounds=3,
        expected_request_bytes=1079,
        expected_response_bytes=800,
        require_complete_application_timing=True,
        require_duplex_application_timing=True,
    )
    assert projection["view"] == DUPLEX_TIMING_ONLY_VIEW
    widths = expected_raw_timing_widths(
        "RELAY", public_r=3, public_q=100, has_relay_duplex=True
    )
    assert widths == (3, 2, 3, 2, 3, 2, 3, 2, 3, 3, 3)
    assert len(timing_feature_vector(projection, raw_widths=widths)) == 162
    assert not any(
        private in projection
        for private in ("real", "request_kind", "operation_id", "provider_state")
    )


def test_strengthened_projection_fails_closed_on_missing_boundary() -> None:
    rows = _duplex_rows()
    del rows[1]["gateway_to_relay_receive_ns"]
    with pytest.raises(ValueError, match="all four"):
        relay_timing_projection(
            {"public_relay_events": rows},
            expected_rounds=3,
            require_complete_application_timing=True,
            require_duplex_application_timing=True,
        )


def test_p10_strengthened_relay_feature_width_is_publicly_fixed() -> None:
    projection = relay_timing_projection(
        {"public_relay_events": _duplex_rows(506)},
        expected_rounds=506,
        require_complete_application_timing=True,
        require_duplex_application_timing=True,
    )
    widths = expected_raw_timing_widths(
        "RELAY", public_r=506, public_q=100, has_relay_duplex=True
    )
    assert sum(widths) == 5562
    assert len(timing_feature_vector(projection, raw_widths=widths)) == 5695


def test_registry_opportunity_clock_ignores_real_count_and_consumer_state() -> None:
    public = {
        "origin_ns": 1_000_000,
        "ordinal": 7,
        "period_ns": 60_000_000,
        "initial_lead_ns": 25_000_000,
        "commitment_lead_ns": 5_000_000,
        "previous_public_send_ns": 386_000_000,
    }
    expected = duplex_pir_opportunity_times(**public)
    for _private_state in (
        "ZERO_REAL",
        "ONE_REAL",
        "MULTIPLE_REAL",
        "CONSUMER_AWAKE",
        "CONSUMER_BLOCKED",
    ):
        assert duplex_pir_opportunity_times(**public) == expected


def test_open_loop_sender_does_not_read_private_completion_for_deadlines() -> None:
    source = inspect.getsource(duplex_pir_opportunity_times)
    assert "completion" not in source
    assert "real" not in source
    assert "descriptor" not in source


def test_expired_real_pir_preparation_is_deferred_not_failed(tmp_path: Path) -> None:
    resolver = OnlineSimplePIRResolver(tmp_path / "pir")
    response = json.dumps(
        {"type": "PIR_DEFERRED", "operation_id": "op-real", "padding": "x"}
    )
    with pytest.raises(RuntimeError, match="expired public opportunity"):
        resolver._decode_query_response("op-real", 10, response)


def test_late_pending_pir_cannot_retroactively_fill_expired_cutoff() -> None:
    source = inspect.getsource(OnlineSimplePIRResolver._run_duplex_cover_schedule)
    assert "self.cover_pending[0].enqueued_ns <= cutoff_ns" in source
    assert '"expired_opportunity_retrofilled": False' in source


def test_private_registry_completion_wait_does_not_bound_public_clock() -> None:
    source = inspect.getsource(OnlineSimplePIRResolver._run_completion_loop)
    assert "timeout_ms=self.cover_liveness_cap_ms" in source
    assert "registry_answer_release_delay_ms + self.cover_period_ms" not in source


def test_gateway_release_lane_only_uses_committed_frame_and_public_write() -> None:
    source = (ROOT / "common_action_gateway_v2/canonicalv9/duplex_response.go").read_text()
    release_body = source.split(
        "func (v *gatewayResponseVirtualizer) releaseCommitted", 1
    )[1].split("func (v *gatewayResponseVirtualizer) setEligibility", 1)[0]
    assert "ReserveEligible" not in release_body
    assert "EncodeKnownLength" not in release_body
    assert "EncapsulateResponse" not in release_body
    assert ".prepared.Send(" in release_body
    assert "WriteHeader(http.StatusOK)" in release_body


def test_gateway_commit_and_release_are_distinct_bounded_lanes() -> None:
    source = (ROOT / "common_action_gateway_v2/canonicalv9/duplex_response.go").read_text()
    assert "preparationJobs := make(chan gatewayResponsePreparationJob, v.rounds)" in source
    assert "go v.releaseCommitted(releasePacer, committed, releaseDone)" in source
    assert "for lane := 0; lane < v.workers; lane++" in source
    assert "request.commit(commitment)" in source


def test_protected_runtime_sizes_and_counts_are_unchanged_in_source() -> None:
    profiles = duplex_timing_candidate_profiles()
    assert {(p.request_final_bytes, p.response_final_bytes) for p in profiles} == {
        (1079, 800)
    }
    assert {p.pir_resolution_opportunities for p in profiles} == {100}


def test_duplex_functional_manifest_freezes_48_fresh_v4r4_identities() -> None:
    freeze = json.loads(
        (ROOT / "V12_DUPLEX_FUNCTIONAL_FREEZE_V5.json").read_text()
    )
    assert freeze["frozen_before_functional_execution"] is True
    assert len(freeze["profiles"]) == 3
    assert len(freeze["frameworks"]) == 2
    assert len(freeze["workloads"]) == 8
    assert freeze["planned_identities"] == 48
    assert freeze["retry_count"] == freeze["replacement_count"] == 0
    assert freeze["identity_suffix"] == "005"
    assert freeze["fixed"]["response_preparation_lead_ms"] == 50
    assert freeze["fixed"]["response_preparation_workers"] == 6
    assert freeze["fixed"]["pir_commitment_lead_ms"] == 20
    assert freeze["protected_classifier_campaign_authorized"] is False
    assert freeze["auc_authorized"] is False
