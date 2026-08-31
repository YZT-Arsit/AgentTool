from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from v11_full_scope.fixtures import tool_case
from v11_full_scope.frameworks import run_framework_case
from v11_online.session import CAUSAL_HORIZON_RUNNER, CanonicalOnlineSession
from v12_timing.capacity import CapacityContract, run_capacity_suite
from v12_timing.profile import (
    EFFECTIVE_PUBLIC_CLOCK_V2,
    causal_horizon_candidate_profiles,
)


ROOT = Path(__file__).resolve().parents[1]


def _model_module():
    path = ROOT / "V12_CAUSAL_HORIZON_CAPACITY_MODEL.py"
    spec = importlib.util.spec_from_file_location("v12_causal_horizon_capacity_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_causal_horizon_candidates_are_exact_and_public() -> None:
    profiles = causal_horizon_candidate_profiles()
    assert [profile.admission_horizon_ms for profile in profiles] == [4500, 5000, 6000]
    assert [profile.admission_rounds for profile in profiles] == [450, 500, 600]
    assert [profile.total_rounds for profile in profiles] == [506, 556, 656]
    assert [profile.scheduled_lifetime_ms for profile in profiles] == [5060, 5560, 6560]
    assert [profile.pir_real_resolution_arrival_cutoff_ms for profile in profiles] == [4089, 4589, 5589]
    assert all(profile.timing_semantic_revision == EFFECTIVE_PUBLIC_CLOCK_V2 for profile in profiles)
    assert all("-V2-" in profile.profile_id for profile in profiles)
    assert all(profile.request_final_bytes == 1079 and profile.response_final_bytes == 800 for profile in profiles)


def test_pir_capacity_passes_all_frozen_horizons() -> None:
    for horizon in (4500, 5000, 6000):
        result = run_capacity_suite(CapacityContract(admission_horizon_ms=horizon))
        assert result["passed"] is True
        assert result["contract"]["K"] == 6
        assert result["contract"]["Q"] == 100


def test_effective_clock_stall_models_preserve_count_and_no_burst() -> None:
    model = _model_module()
    for stalls in ({}, {3: 35_000_000}, {3: 100_000_000}, {3: 35_000_000, 20: 100_000_000}):
        result = model.stall_model(50, stalls)
        assert result["fixed_slot_count"] == 50
        assert result["no_catch_up_burst"] is True


def test_private_readiness_cannot_change_effective_schedule() -> None:
    model = _model_module()
    observed = {1: 10_000_000, 2: 55_000_000, 3: 65_000_000}
    first = model.effective_schedule(rounds=8, first_deadline_ns=10_000_000, period_ns=10_000_000, observed_dispatch=observed)
    second = model.effective_schedule(rounds=8, first_deadline_ns=10_000_000, period_ns=10_000_000, observed_dispatch=observed)
    assert first == second


def test_frozen_candidate_file_precedes_live_execution() -> None:
    value = json.loads((ROOT / "V12_CAUSAL_HORIZON_CANDIDATES_FREEZE.json").read_text(encoding="utf-8"))
    assert value["frozen_before_implementation"] is True
    assert [item["horizon_ms"] for item in value["candidates"]] == [4500, 5000, 6000]
    assert value["timing_attack_sessions"] == 0


@pytest.mark.skipif(not CAUSAL_HORIZON_RUNNER.is_file(), reason="Linux causal-horizon runner unavailable")
def test_actual_v2_profile_uses_effective_clock_runner_and_full_transcript(tmp_path: Path) -> None:
    profile = causal_horizon_candidate_profiles()[0]
    case = replace(
        tool_case("DEV-CHR-COMPONENT-V2-R2-001", "OpenAI Agents SDK"),
        capability="tool.read",
    )
    with CanonicalOnlineSession(tmp_path / "canonical", [case], public_profile=profile) as session:
        outcome = run_framework_case(case, session.implementation())
    assert session.runner_binary == CAUSAL_HORIZON_RUNNER
    assert outcome.operation_outcome_semantics == "READ_ONLY:SUCCESS"
    assert session.trace is not None
    assert session.trace["session_status"] == "COMPLETE"
    assert session.trace["emitted_cells"] == 506
    assert len(session.trace["public_relay_events"]) == 506
    assert session.trace.get("resolved_not_admitted_ids", []) == []
