from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_v12_duplex_functional import build_workload
from scripts.run_v12_v4r7_bounded_liveness_functional import (
    _capacity_workflow_runner,
)
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import run_online_framework_workflow
from v12_timing.profile import duplex_provider_bound_p10_profile

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


def test_m_is_count_capacity_not_causal_depth_guarantee() -> None:
    profile = duplex_provider_bound_p10_profile()
    assert profile.maximum_real_operations == 50
    assert profile.admission_rounds == 450
    assert profile.result_capacity_rounds == 50
    assert profile.total_rounds == 521


def test_historical_causal_depth_inventory_reconciles() -> None:
    contract = json.loads(
        (ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    historical = contract["historical_causal_depth_50"]
    assert historical["intended"] == 50
    assert historical["admitted_before_public_admission_window_closed"] == 39
    assert historical["resolved_after_window_not_admitted"] == 11
    assert historical["silently_lost"] == 0
    assert historical["all_intents_explicitly_accounted"] is True
    assert contract["m_does_not_imply_causal_depth_guarantee"] is True


def test_fresh_functional_identity_inventory_is_frozen() -> None:
    freeze = json.loads(
        (ROOT / "V12_V4R7_BOUNDED_LIVENESS_FUNCTIONAL_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )
    identities = [row["identity"] for row in freeze["identities"]]
    assert freeze["planned_units"] == len(identities) == 16
    assert len(set(identities)) == 16
    assert "DEV-DTVR-V4R7-P10-B200-OA-CAUSAL_DEPTH_50-001" not in identities
    assert freeze["execution_policy"]["retries"] == 0


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_capacity_50_is_one_parallel_framework_turn(framework: str) -> None:
    workflow, cases = build_workload("CAPACITY_50", framework, f"fixture-{framework}")
    assert workflow == "PARALLEL_ACTIONS"
    assert len(cases) == 50
    assert len({case.operation_id for case in cases}) == 50


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_capacity_50_native_framework_executes_every_operation(framework: str) -> None:
    workflow, cases = build_workload("CAPACITY_50", framework, f"native-{framework}")
    result = (
        run_online_framework_workflow(framework, workflow, cases, native_implementation)
        if framework == "OpenAI Agents SDK"
        else _capacity_workflow_runner(
            framework, workflow, cases, native_implementation
        )
    )
    trajectory = result["projection"]["trajectory"]
    assert [row["operation_id"] for row in trajectory] == [
        case.operation_id for case in cases
    ]
    assert len(trajectory) == 50
