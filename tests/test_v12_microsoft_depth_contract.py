from __future__ import annotations

from dataclasses import replace

import pytest

from v11_full_scope.fixtures import agent_case, tool_case
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import AgentServiceSubtype
from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    OPENAI_NATIVE_MAX_TURNS_PUBLIC,
    SYSTEM_MAX_REAL_OPERATIONS_PUBLIC,
    run_online_framework_workflow,
)


MICROSOFT = "Microsoft Agent Framework"
OPENAI = "OpenAI Agents SDK"


def _cases(framework: str, count: int, label: str):
    return [
        replace(
            tool_case(f"DEV-MDC-{label}-{index:02d}", framework),
            operation_id=f"opDEVMD{label}{index:04d}",
            logical_action_name="repeated_native_depth_tool",
            arguments={"city": f"value-{index}"},
        ).validate()
        for index in range(count)
    ]


def _assert_native_result(value: dict, cases: list) -> None:
    trajectory = value["projection"]["trajectory"]
    assert [item["operation_id"] for item in trajectory] == [case.operation_id for case in cases]
    assert [item["logical_action"] for item in trajectory] == [case.logical_action_name for case in cases]
    assert [item["result"] for item in trajectory] == [
        native_implementation(case, case.arguments).result for case in cases
    ]
    assert value["projection"]["final_framework_state"] == "framework-completed:DYNAMIC_SEQUENCE"


@pytest.mark.parametrize("count", [1, 30, 40, 41, 50])
def test_microsoft_public_iteration_bound_executes_native_boundary(count: int) -> None:
    cases = _cases(MICROSOFT, count, f"MSBOUND{count:02d}")
    value = run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", cases, native_implementation)
    _assert_native_result(value, cases)
    assert len(value["observed_function_results"]) == count
    assert value["private_execution_configuration"] == {
        "max_iterations": MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
        "max_function_calls": SYSTEM_MAX_REAL_OPERATIONS_PUBLIC,
        "source": "PUBLIC_MAX_REAL_OPERATIONS",
    }


def test_microsoft_fifty_actions_include_final_framework_response() -> None:
    cases = _cases(MICROSOFT, 50, "MSFINAL50")
    value = run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", cases, native_implementation)
    _assert_native_result(value, cases)
    assert value["projection"]["final_framework_state"] == "framework-completed:DYNAMIC_SEQUENCE"


def test_fifty_first_real_operation_is_rejected_by_public_system_capacity() -> None:
    cases = _cases(MICROSOFT, 51, "MSREJECT51")
    invoked: list[str] = []

    def should_not_run(case, values):
        invoked.append(case.operation_id)
        return native_implementation(case, values)

    with pytest.raises(ValueError, match="PROFILE_CAPACITY_EXCEEDED"):
        run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", cases, should_not_run)
    assert invoked == []
    assert MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC == 50
    assert SYSTEM_MAX_REAL_OPERATIONS_PUBLIC == 50


def test_microsoft_iteration_configuration_is_secret_independent() -> None:
    ordinary = _cases(MICROSOFT, 2, "MSCONFIGORD")
    rare = [replace(case, logical_action_name=f"rare_{index}", agent_id=index + 10).validate() for index, case in enumerate(ordinary)]
    repeated = _cases(MICROSOFT, 7, "MSCONFIGREP")
    child = replace(
        agent_case("DEV-MDC-MSCONFIGAAT", MICROSOFT, AgentServiceSubtype.AGENT_AS_TOOL),
        operation_id="opDEVMDMSCONFIGAAT0001",
    ).validate()
    agent_as_tool = [ordinary[0], child]
    records = [
        run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", ordinary, native_implementation),
        run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", rare, native_implementation),
        run_online_framework_workflow(MICROSOFT, "DYNAMIC_SEQUENCE", repeated, native_implementation),
        run_online_framework_workflow(MICROSOFT, "TOOL_TO_AGENT_AS_TOOL", agent_as_tool, native_implementation),
    ]
    assert {tuple(sorted(record["private_execution_configuration"].items())) for record in records} == {
        tuple(
            sorted(
                {
                    "max_iterations": 50,
                    "max_function_calls": 50,
                    "source": "PUBLIC_MAX_REAL_OPERATIONS",
                }.items()
            )
        )
    }


@pytest.mark.parametrize("count", [1, 10, 50])
def test_openai_turn_bound_is_fixed_public_profile_value(count: int) -> None:
    cases = _cases(OPENAI, count, f"OACONFIG{count:02d}")
    value = run_online_framework_workflow(OPENAI, "DYNAMIC_SEQUENCE", cases, native_implementation)
    _assert_native_result(value, cases)
    assert value["private_execution_configuration"] == {
        "max_turns": OPENAI_NATIVE_MAX_TURNS_PUBLIC,
        "source": "PUBLIC_MAX_REAL_OPERATIONS_PLUS_TWO",
    }
    assert OPENAI_NATIVE_MAX_TURNS_PUBLIC == 52
