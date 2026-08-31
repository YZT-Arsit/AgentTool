from __future__ import annotations

from unittest.mock import Mock

import pytest

from canonical_v9.runner import descriptor
from v11_online.session import OnlineSimplePIRResolver
from v12_timing.capacity import CapacityContract, ResolutionArrival, run_capacity_suite, simulate_arrivals
from v12_timing.profile import TimingIndistinguishabilityProfile


def _profile() -> TimingIndistinguishabilityProfile:
    return TimingIndistinguishabilityProfile(
        profile_id="V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        round_period_ms=10,
        pir_resolution_period_ms=60,
    ).validate()


def test_fixed_epoch_derives_query_count_and_joint_cutoff() -> None:
    profile = _profile()
    assert profile.pir_public_epoch_ms == 6000
    assert profile.pir_resolution_opportunities == 100
    assert profile.maximum_real_agent_resolutions == 6
    assert profile.pir_real_resolution_arrival_cutoff_ms == 2589


def test_adversarial_causal_capacity_suite_passes() -> None:
    result = run_capacity_suite()
    assert result["passed"] is True
    assert set(result["traces"]) == {
        "all_K_immediate",
        "first_near_latest_supported_boundary",
        "one_after_each_prior_resolution_result",
        "arrivals_immediately_after_cover_opportunity",
        "multiple_pending_bursts",
        "cache_hits_mixed_with_new_resolutions",
    }


def test_real_resolution_after_public_cutoff_fails_closed() -> None:
    contract = CapacityContract()
    result = simulate_arrivals(
        [ResolutionArrival("late", 10, contract.latest_real_arrival_ms + 0.001)], contract
    )
    assert result["passed"] is False
    assert result["failures"] == ["PIR_REAL_RESOLUTION_ARRIVAL_CUTOFF_EXCEEDED"]


def test_authenticated_descriptor_is_reused_within_same_epoch(tmp_path) -> None:
    resolver = OnlineSimplePIRResolver(tmp_path / "pir")
    raw = Mock(side_effect=lambda _operation_id, index: descriptor(index))
    resolver.query = raw
    first = resolver.resolve_descriptor("op-1", 10)
    second = resolver.resolve_descriptor("op-2", 10)
    third = resolver.resolve_descriptor("op-3", 21)
    assert first == second == descriptor(10)
    assert third == descriptor(21)
    assert raw.call_count == 2
    assert resolver.descriptor_cache_hits == 1
    assert resolver.descriptor_cache_misses == 2


def test_cover_schedule_rejects_old_q_equals_m_rule(tmp_path) -> None:
    resolver = OnlineSimplePIRResolver(tmp_path / "pir")
    with pytest.raises(ValueError, match="epoch / period"):
        resolver.start_cover_schedule(opportunities=50, period_ms=60, epoch_ms=6000)
