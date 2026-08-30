from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Awaitable, Mapping, MutableSequence
from typing import Any, Callable

from v11_full_scope.frameworks import (
    _make_structured_function,
    _openai_call,
    _openai_final,
)
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily, V11ActionCase, V11ActionOutcome


Implementation = Callable[[V11ActionCase, dict[str, Any]], V11ActionOutcome]
PRIVATE_ROUTED_CALLABLE_PREFIX = "acv_private_route_"


def _private_routed_names(cases: list[V11ActionCase]) -> list[str]:
    """Return injective framework-only callable names for one private registry."""

    operation_ids = [case.operation_id for case in cases]
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("online workflow operation IDs must be unique")
    return [f"{PRIVATE_ROUTED_CALLABLE_PREFIX}{index:03d}" for index in range(len(cases))]


def _ordered_outcomes(
    framework: str,
    cases: list[V11ActionCase],
    executed_operation_ids: list[str],
    outcomes_by_operation: dict[str, V11ActionOutcome],
) -> list[V11ActionOutcome]:
    expected = [case.operation_id for case in cases]
    if Counter(expected) != Counter(executed_operation_ids):
        raise AssertionError(
            f"{framework} online workflow operation-ID execution mismatch: "
            f"expected={expected!r} executed={executed_operation_ids!r}"
        )
    if Counter(expected) != Counter(outcomes_by_operation.keys()):
        raise AssertionError(
            f"{framework} online workflow outcome mapping mismatch: "
            f"expected={expected!r} outcomes={list(outcomes_by_operation)!r}"
        )
    if len(executed_operation_ids) != len(cases):
        raise AssertionError(f"{framework} online workflow did not execute every action exactly once")
    return [outcomes_by_operation[case.operation_id] for case in cases]


def prewarm_framework(framework: str) -> None:
    """Load pinned framework machinery before the public session starts."""

    if framework == "OpenAI Agents SDK":
        import agents  # noqa: F401
        from agents.testing import ScriptedModel  # noqa: F401
    elif framework == "Microsoft Agent Framework":
        import agent_framework  # noqa: F401
    else:
        raise ValueError("unknown pinned framework")


def trajectory_projection(cases: list[V11ActionCase], outcomes: list[V11ActionOutcome], final_output: str) -> dict[str, Any]:
    if len(cases) != len(outcomes):
        raise AssertionError("framework trajectory did not execute every action exactly once")
    return {
        "trajectory": [
            {
                "operation_id": case.operation_id,
                "logical_action": case.logical_action_name,
                "arguments": case.argument_schema.validate_values(case.arguments),
                "causal_parent": cases[index - 1].operation_id if index else None,
                "provider_visible_logical_request": outcome.provider_visible_logical_request,
                "effect_count": outcome.effect_count,
                "outcome": outcome.outcome_semantics,
                "result": outcome.result,
            }
            for index, (case, outcome) in enumerate(zip(cases, outcomes, strict=True))
        ],
        "framework_visible_intermediate_results": [outcome.result for outcome in outcomes],
        "final_framework_state": final_output,
    }


async def _run_openai(cases: list[V11ActionCase], implementation: Implementation, workflow: str) -> dict[str, Any]:
    from agents import Agent, RunConfig, Runner, function_tool, handoff
    from agents.items import HandoffOutputItem, ToolCallOutputItem
    from agents.testing import ModelStep, ScriptedModel

    outcomes: list[V11ActionOutcome] = []
    executed_operation_ids: list[str] = []
    outcomes_by_operation: dict[str, V11ActionOutcome] = {}
    boundary: list[tuple[str, Any]] = []
    routed_names = _private_routed_names(cases)
    routed_name_by_operation = {
        case.operation_id: routed_name
        for case, routed_name in zip(cases, routed_names, strict=True)
    }

    def ordinary_tool(case: V11ActionCase, routed_name: str):
        def invoke(value_case: V11ActionCase, values: dict[str, Any]) -> V11ActionOutcome:
            outcome = implementation(value_case, values)
            outcomes.append(outcome)
            executed_operation_ids.append(value_case.operation_id)
            outcomes_by_operation[value_case.operation_id] = outcome
            return outcome

        function = _make_structured_function(case, invoke, boundary)
        return function_tool(function, name_override=routed_name)

    final_text = f"framework-completed:{workflow}"
    if workflow in {"TOOL_TO_TOOL", "DYNAMIC_SEQUENCE", "INTERNAL_TO_EXTERNAL", "EXTERNAL_TO_INTERNAL", "PARALLEL_ACTIONS", "MIXED_PARALLEL"}:
        tools = [ordinary_tool(case, routed_name_by_operation[case.operation_id]) for case in cases]
        if workflow == "PARALLEL_ACTIONS":
            call_steps = [[_openai_call(routed_name_by_operation[case.operation_id], case.arguments, case.operation_id) for case in cases]]
        elif workflow == "MIXED_PARALLEL":
            midpoint = max(1, len(cases) // 2)
            call_steps = [
                [_openai_call(routed_name_by_operation[case.operation_id], case.arguments, case.operation_id) for case in cases[:midpoint]],
                [_openai_call(routed_name_by_operation[case.operation_id], case.arguments, case.operation_id) for case in cases[midpoint:]],
            ]
        else:
            call_steps = [[_openai_call(routed_name_by_operation[case.operation_id], case.arguments, case.operation_id)] for case in cases]
        model = ScriptedModel(call_steps + [[_openai_final(final_text)]])
        agent = Agent(name="V11_2OnlineToolSequence", instructions="Execute actions causally.", model=model, tools=tools)
        result = await Runner.run(
            agent,
            "online-development",
            max_turns=max(10, len(cases) + 2),
            run_config=RunConfig(tracing_disabled=True),
        )
        final_output = str(result.final_output)
        tool_outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    elif workflow in {"TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL"}:
        agent_case = next(case for case in cases if case.agent_service_subtype is AgentServiceSubtype.AGENT_AS_TOOL)
        tool_case = next(case for case in cases if case.action_family is CanonicalActionFamily.TOOL)

        async def child_response(_call):
            outcome = implementation(agent_case, agent_case.argument_schema.validate_values(agent_case.arguments))
            outcomes.append(outcome)
            executed_operation_ids.append(agent_case.operation_id)
            outcomes_by_operation[agent_case.operation_id] = outcome
            return [_openai_final(outcome.result)]

        child_model = ScriptedModel([ModelStep.respond(child_response)])
        child = Agent(name="V11_2OnlineChild", instructions="Return mediated child result.", model=child_model)
        child_tool = child.as_tool(
            tool_name=routed_name_by_operation[agent_case.operation_id],
            tool_description="Private child Agent service",
        )
        registered = ordinary_tool(tool_case, routed_name_by_operation[tool_case.operation_id])
        ordered_calls = []
        for case in cases:
            if case is agent_case:
                ordered_calls.append([_openai_call(child_tool.name, {"input": str(next(iter(case.arguments.values())))}, case.operation_id)])
            else:
                ordered_calls.append([_openai_call(routed_name_by_operation[case.operation_id], case.arguments, case.operation_id)])
        model = ScriptedModel(ordered_calls + [[_openai_final(final_text)]])
        agent = Agent(name="V11_2OnlineAgentToolSequence", instructions="Execute actions causally.", model=model, tools=[registered, child_tool])
        result = await Runner.run(agent, "online-development", run_config=RunConfig(tracing_disabled=True))
        final_output = str(result.final_output)
        tool_outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    elif workflow == "TOOL_TO_HANDOFF":
        tool_case, handoff_case = cases
        registered = ordinary_tool(tool_case, routed_name_by_operation[tool_case.operation_id])

        async def target_response(_call):
            outcome = implementation(handoff_case, handoff_case.argument_schema.validate_values(handoff_case.arguments))
            outcomes.append(outcome)
            executed_operation_ids.append(handoff_case.operation_id)
            outcomes_by_operation[handoff_case.operation_id] = outcome
            return [_openai_final(outcome.result)]

        target_model = ScriptedModel([ModelStep.respond(target_response)])
        target = Agent(name="V11_2OnlineHandoffTarget", instructions="Return mediated handoff result.", model=target_model)
        handoff_object = handoff(target)
        source_model = ScriptedModel(
            [
                [_openai_call(routed_name_by_operation[tool_case.operation_id], tool_case.arguments, tool_case.operation_id)],
                [_openai_call(handoff_object.tool_name, {}, handoff_case.operation_id)],
            ]
        )
        source = Agent(
            name="V11_2OnlineHandoffSource",
            instructions="Execute Tool then hand off.",
            model=source_model,
            tools=[registered],
            handoffs=[handoff_object],
        )
        result = await Runner.run(source, "online-development", run_config=RunConfig(tracing_disabled=True))
        final_output = str(result.final_output)
        tool_outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
        if len([item for item in result.new_items if isinstance(item, HandoffOutputItem)]) != 1:
            raise AssertionError("OpenAI online handoff boundary was not reached exactly once")
    else:
        raise ValueError(f"unsupported OpenAI online workflow: {workflow}")

    ordered_outcomes = _ordered_outcomes(
        "OpenAI", cases, executed_operation_ids, outcomes_by_operation
    )
    return {
        "framework": "OpenAI Agents SDK",
        "workflow": workflow,
        "projection": trajectory_projection(cases, ordered_outcomes, final_output),
        "tool_output_count": len(tool_outputs),
        "native_framework_api": "agents.Runner.run",
    }


class _MicrosoftSequenceClient:
    def __new__(cls, calls: list[tuple[str, dict[str, Any], str]], final_text: str):
        from agent_framework import BaseChatClient, FunctionInvocationLayer

        class Client(FunctionInvocationLayer[Any], BaseChatClient[Any]):
            def __init__(self) -> None:
                super().__init__(middleware=[])
                self.iteration = 0
                self.observed_results: list[str] = []

            def _inner_get_response(
                self,
                *,
                messages: MutableSequence[Any],
                stream: bool,
                options: Mapping[str, Any],
                **_kwargs: Any,
            ) -> Awaitable[Any]:
                if stream:
                    raise NotImplementedError("V11.2 Microsoft online parent is non-streaming")

                async def response():
                    from agent_framework import ChatResponse, Content, Message

                    for message in messages:
                        for content in getattr(message, "contents", []):
                            if getattr(content, "type", "") == "function_result":
                                value = str(getattr(content, "result", None))
                                if value not in self.observed_results:
                                    self.observed_results.append(value)
                    if self.iteration < len(calls):
                        name, arguments, operation_id = calls[self.iteration]
                        value = ChatResponse(
                            messages=Message(
                                "assistant",
                                [Content.from_function_call(call_id=operation_id, name=name, arguments=arguments)],
                            )
                        )
                    else:
                        value = ChatResponse(messages=Message("assistant", [final_text]))
                    self.iteration += 1
                    return value

                return response()

        return Client()


async def _run_microsoft(cases: list[V11ActionCase], implementation: Implementation, workflow: str) -> dict[str, Any]:
    from agent_framework import Agent, tool

    outcomes: list[V11ActionOutcome] = []
    executed_operation_ids: list[str] = []
    outcomes_by_operation: dict[str, V11ActionOutcome] = {}
    boundary: list[tuple[str, Any]] = []
    registered: list[Any] = []
    calls: list[tuple[str, dict[str, Any], str]] = []
    routed_names = _private_routed_names(cases)
    for case, routed_name in zip(cases, routed_names, strict=True):
        if case.agent_service_subtype is AgentServiceSubtype.HANDOFF:
            raise NotImplementedError("FRAMEWORK_NATIVE_MECHANISM_ABSENT")
        if case.agent_service_subtype is AgentServiceSubtype.AGENT_AS_TOOL:
            from v11_full_scope.frameworks import _MicrosoftChildClient
            agent_case = case

            def child_implementation(value_case: V11ActionCase, values: dict[str, Any]) -> V11ActionOutcome:
                outcome = implementation(value_case, values)
                outcomes.append(outcome)
                executed_operation_ids.append(value_case.operation_id)
                outcomes_by_operation[value_case.operation_id] = outcome
                return outcome

            child = Agent(
                client=_MicrosoftChildClient(agent_case, child_implementation),
                name=f"V11_2Child_{agent_case.case_id}",
                instructions="Return mediated result",
            )
            child_tool = child.as_tool(name=routed_name, arg_name="task", approval_mode="never_require")
            registered.append(child_tool)
            calls.append((child_tool.name, {"task": str(next(iter(agent_case.arguments.values())))}, agent_case.operation_id))
        else:
            def invoke(value_case: V11ActionCase, values: dict[str, Any]) -> V11ActionOutcome:
                outcome = implementation(value_case, values)
                outcomes.append(outcome)
                executed_operation_ids.append(value_case.operation_id)
                outcomes_by_operation[value_case.operation_id] = outcome
                return outcome

            function = _make_structured_function(case, invoke, boundary)
            registered.append(tool(name=routed_name, approval_mode="never_require")(function))
            calls.append((routed_name, case.arguments, case.operation_id))

    final_text = f"framework-completed:{workflow}"
    client = _MicrosoftSequenceClient(calls, final_text)
    parent = Agent(client=client, name="V11_2MicrosoftOnline", instructions="Execute actions causally.", tools=registered)
    result = await parent.run("online-development")
    ordered_outcomes = _ordered_outcomes(
        "Microsoft", cases, executed_operation_ids, outcomes_by_operation
    )
    return {
        "framework": "Microsoft Agent Framework",
        "workflow": workflow,
        "projection": trajectory_projection(cases, ordered_outcomes, result.text),
        "observed_function_results": client.observed_results,
        "native_framework_api": "agent_framework.Agent.run",
    }


def run_online_framework_workflow(
    framework: str,
    workflow: str,
    cases: list[V11ActionCase],
    implementation: Implementation,
) -> dict[str, Any]:
    for case in cases:
        case.validate()
        if case.framework != framework:
            raise ValueError("online workflow case framework mismatch")
    if framework == "OpenAI Agents SDK":
        coroutine = _run_openai(cases, implementation, workflow)
    elif framework == "Microsoft Agent Framework":
        coroutine = _run_microsoft(cases, implementation, workflow)
    else:
        raise ValueError("online framework workflow requires a pinned native framework")
    return asyncio.run(coroutine)
