from __future__ import annotations

import inspect
from pathlib import Path

from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import (
    DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6,
    duplex_response_closure_p10_profile,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v4r6_p10_public_response_lag_is_frozen() -> None:
    profile = duplex_response_closure_p10_profile()
    assert profile.profile_id == "V12-TIMING-INDIST-V4R6-H50-H4500-P10-PIR60"
    assert profile.timing_semantic_revision == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6
    assert profile.response_public_lag_ms == 30
    assert profile.response_preparation_lead_ms == 20
    assert profile.total_rounds == 506
    assert profile.request_final_bytes == 1079
    assert profile.response_final_bytes == 800
    assert profile.pir_resolution_opportunities == 100


def test_v4r6_go_plan_exposes_public_lag_without_private_inputs() -> None:
    plan = duplex_response_closure_p10_profile().go_plan_fields()
    assert plan["response_public_lag_ms"] == 30
    assert plan["response_preparation_lead_ms"] == 20
    assert plan["response_preparation_workers"] == 6
    assert not any(
        private in plan
        for private in ("action_kind", "provider_readiness", "real", "result_kind")
    )


def test_v4r6_uses_duplex_runner() -> None:
    source = inspect.getsource(CanonicalOnlineSession.__init__)
    assert '"DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6"' in source


def test_response_release_miss_waits_and_writes_instead_of_dropping() -> None:
    source = (
        ROOT / "common_action_gateway_v2/canonicalv9/duplex_response.go"
    ).read_text(encoding="utf-8")
    release = source.split(
        "func (v *gatewayResponseVirtualizer) releaseCommitted", 1
    )[1].split("func (v *gatewayResponseVirtualizer) setEligibility", 1)[0]
    assert "preparedResult = <-item.prepared" in release
    assert "duplex Gateway response preparation missed public release" not in release
    assert "WriteCompleted" in release
    assert "ReleaseSlipNS" in release


def test_transcript_complete_requires_successful_application_visible_slots() -> None:
    source = (
        ROOT / "common_action_gateway_v2/canonicalv9/online.go"
    ).read_text(encoding="utf-8")
    assert "exactRelayPublicSlotInventory(relayEvents, plan.Rounds)" in source
    assert "EmittedCells: successfulWrites" in source
    assert "PublicTranscriptComplete: transcriptComplete" in source
    assert "RelayApplicationReceivedCells: len(relayEvents)" in source


def test_fixed_worker_lanes_are_ready_before_clock_constructor_returns() -> None:
    source = (
        ROOT / "common_action_gateway_v2/canonicalv9/duplex_response.go"
    ).read_text(encoding="utf-8")
    workers = source.index("workersReady :=")
    ready = source.index("ready <- nil", workers)
    wait = source.index("<-workersReady", workers)
    assert workers < wait < ready

