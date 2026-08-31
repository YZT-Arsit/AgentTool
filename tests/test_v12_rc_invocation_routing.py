from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from v11_full_scope.fixtures import agent_case, tool_case
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import AgentServiceSubtype
from v11_online.frameworks import (
    PRIVATE_ROUTED_CALLABLE_PREFIX,
    _private_routed_names,
    run_online_framework_workflow,
)
from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    TrajectorySpec,
    run_canonical_online_trajectory_case,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_4-runner"
PERMIT = ExecutionPermit("V11A_DEVELOPMENT_REGRESSION", True)
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


def _case(case_id: str, framework: str, *, value: str = "Paris", effect: str = "READ_ONLY"):
    capability = {
        "READ_ONLY": "tool.read",
        "IDEMPOTENT_EFFECT": "tool.idem",
        "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
    }[effect]
    return replace(
        tool_case(case_id, framework, effect_semantics=effect),
        arguments={"city": value},
        capability=capability,
    )


def _run(framework: str, cases, workflow: str = "DYNAMIC_SEQUENCE"):
    return run_online_framework_workflow(framework, workflow, list(cases), native_implementation)


def _assert_exact_projection(value: dict, cases) -> None:
    trajectory = value["projection"]["trajectory"]
    expected_ids = [case.operation_id for case in cases]
    assert Counter(item["operation_id"] for item in trajectory) == Counter(expected_ids)
    assert len({item["operation_id"] for item in trajectory}) == len(cases)
    assert [item["logical_action"] for item in trajectory] == [
        case.logical_action_name for case in cases
    ]
    assert [item["arguments"] for item in trajectory] == [case.arguments for case in cases]
    if value["framework"] == "OpenAI Agents SDK":
        assert value["tool_output_count"] == len(cases)
    else:
        assert len(value["observed_function_results"]) == len(cases)
    encoded = json.dumps(value, sort_keys=True)
    assert PRIVATE_ROUTED_CALLABLE_PREFIX not in encoded
    for item in trajectory:
        assert PRIVATE_ROUTED_CALLABLE_PREFIX not in json.dumps(
            item["provider_visible_logical_request"], sort_keys=True
        )


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("same_arguments", [False, True])
def test_sequential_duplicate_logical_tool_routes_by_operation(
    framework: str, same_arguments: bool, caplog: pytest.LogCaptureFixture
) -> None:
    cases = (
        _case(f"DEV-V12-NTRC2-seq-{framework[:2]}-A-{same_arguments}", framework, value="Paris"),
        _case(
            f"DEV-V12-NTRC2-seq-{framework[:2]}-B-{same_arguments}",
            framework,
            value="Paris" if same_arguments else "Tokyo",
        ),
    )
    assert cases[0].logical_action_name == cases[1].logical_action_name
    assert cases[0].operation_id != cases[1].operation_id
    with caplog.at_level(logging.WARNING):
        value = _run(framework, cases)
    _assert_exact_projection(value, cases)
    assert "Tool name collision detected" not in caplog.text


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_ten_repeated_logical_tools_preserve_every_operation(framework: str) -> None:
    cases = tuple(
        _case(f"DEV-V12-NTRC2-ten-{framework[:2]}-{index:02d}", framework, value=f"value-{index}")
        for index in range(10)
    )
    assert len({case.logical_action_name for case in cases}) == 1
    _assert_exact_projection(_run(framework, cases), cases)


def test_openai_parallel_duplicate_logical_tools_preserve_every_operation() -> None:
    framework = "OpenAI Agents SDK"
    cases = tuple(
        _case(f"DEV-V12-NTRC2-parallel-{index}", framework, value=f"parallel-{index}")
        for index in range(3)
    )
    _assert_exact_projection(_run(framework, cases, "PARALLEL_ACTIONS"), cases)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_same_logical_name_can_have_different_capabilities_and_effects(framework: str) -> None:
    cases = (
        _case(f"DEV-V12-NTRC2-effects-{framework[:2]}-read", framework, effect="READ_ONLY"),
        _case(
            f"DEV-V12-NTRC2-effects-{framework[:2]}-idem",
            framework,
            effect="IDEMPOTENT_EFFECT",
        ),
    )
    value = _run(framework, cases)
    _assert_exact_projection(value, cases)
    trajectory = value["projection"]["trajectory"]
    assert trajectory[0]["outcome"] == "READ_ONLY:SUCCESS"
    assert trajectory[1]["outcome"] == "IDEMPOTENT_EFFECT:SUCCESS"
    assert trajectory[0]["effect_count"] == 0
    assert trajectory[1]["effect_count"] == 1


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize(
    "workflow", ["TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL"]
)
def test_tool_and_agent_as_tool_share_private_routing_namespace(
    framework: str, workflow: str
) -> None:
    ordinary = _case(f"DEV-V12-NTRC2-mixed-{framework[:2]}-tool", framework)
    child = replace(
        agent_case(
            f"DEV-V12-NTRC2-mixed-{framework[:2]}-agent",
            framework,
            AgentServiceSubtype.AGENT_AS_TOOL,
        ),
        logical_action_name=ordinary.logical_action_name,
    )
    cases = (ordinary, child) if workflow == "TOOL_TO_AGENT_AS_TOOL" else (child, ordinary)
    value = _run(framework, cases, workflow)
    _assert_exact_projection(value, cases)


def test_private_routing_names_are_injective_and_not_operation_derived() -> None:
    cases = [
        _case("DEV-V12-NTRC2-route-A", "OpenAI Agents SDK"),
        _case("DEV-V12-NTRC2-route-B", "OpenAI Agents SDK"),
    ]
    names = _private_routed_names(cases)
    assert names == ["acv_private_route_000", "acv_private_route_001"]
    assert len(names) == len(set(names))
    assert all(case.operation_id not in name for case in cases for name in names)


@pytest.mark.skipif(os.name != "posix", reason="canonical V12 runner is frozen for Linux")
@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_private_routing_alias_absent_from_canonical_public_and_private_views(
    tmp_path: Path, framework: str
) -> None:
    cases = tuple(
        _case(f"DEV-V12-NTRC2-public-{framework[:2]}-{index}", framework, value=f"v-{index}")
        for index in range(2)
    )
    spec = TrajectorySpec(
        f"DEV-V12-NTRC2-public-{framework[:2]}", framework, "DYNAMIC_SEQUENCE", cases
    )
    value = run_canonical_online_trajectory_case(
        spec, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert value["causal_proof"]["passed"]
    _assert_exact_projection(value["semantic"], cases)
    for field in (
        "raw_trace",
        "strict_structural_projection",
        "strict_size_projection",
    ):
        assert PRIVATE_ROUTED_CALLABLE_PREFIX not in json.dumps(value[field], sort_keys=True)


def test_duplicate_operation_ids_are_rejected_before_framework_construction() -> None:
    first = _case("DEV-V12-NTRC2-duplicate-op-A", "OpenAI Agents SDK")
    second = replace(
        _case("DEV-V12-NTRC2-duplicate-op-B", "OpenAI Agents SDK"),
        operation_id=first.operation_id,
    )
    with pytest.raises(ValueError, match="operation IDs must be unique"):
        _private_routed_names([first, second])
