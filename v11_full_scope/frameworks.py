from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable, Awaitable, Mapping, MutableSequence, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable

from .models import (
    AgentServiceSubtype,
    ArgumentSchema,
    V11ActionCase,
    V11ActionOutcome,
    V11SemanticRecord,
)


V11Implementation = Callable[[V11ActionCase, dict[str, Any]], V11ActionOutcome]


@dataclass(frozen=True)
class BoundedObject:
    label: str
    count: int
    enabled: bool


def _annotation(value: str) -> str:
    return {
        "str": "str",
        "int": "int",
        "bool": "bool",
        "optional_str": "str | None",
        "object": "BoundedObject",
    }[value]


def _make_structured_function(
    case: V11ActionCase,
    implementation: V11Implementation,
    boundary: list[tuple[str, Any]],
):
    """Create one generic function from the frozen schema, never per-case logic."""

    case.validate()

    def dispatch(values: dict[str, Any]) -> str:
        normalized = {
            key: asdict(value) if is_dataclass(value) else value
            for key, value in values.items()
        }
        validated = case.argument_schema.validate_values(normalized)
        boundary.append(("ACTION_BOUNDARY", validated))
        outcome = implementation(case, validated)
        boundary.append(("ACTION_RESULT", outcome))
        return outcome.result

    parameters = []
    pairs = []
    for field in case.argument_schema.fields:
        suffix = " = None" if field.primitive_type == "optional_str" else ""
        parameters.append(f"{field.name}: {_annotation(field.primitive_type)}{suffix}")
        pairs.append(f"{field.name!r}: {field.name}")
    namespace: dict[str, Any] = {"_dispatch": dispatch, "BoundedObject": BoundedObject}
    source = (
        f"def {case.logical_action_name}({', '.join(parameters)}) -> str:\n"
        f"    return _dispatch({{{', '.join(pairs)}}})\n"
    )
    exec(compile(source, "<v11-generic-structured-tool>", "exec"), namespace)  # noqa: S102
    return namespace[case.logical_action_name]


def _openai_final(text: str):
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText

    return ResponseOutputMessage(
        id="final",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(text=text, type="output_text", annotations=[], logprobs=[])],
    )


def _openai_call(name: str, arguments: dict[str, Any], call_id: str):
    from openai.types.responses import ResponseFunctionToolCall

    return ResponseFunctionToolCall(
        type="function_call",
        name=name,
        call_id=call_id,
        arguments=json.dumps(arguments, sort_keys=True),
    )


def _record(
    case: V11ActionCase,
    outcome: V11ActionOutcome,
    final_output: str,
    framework_result_received: bool,
    evidence: dict[str, Any],
) -> V11SemanticRecord:
    return V11SemanticRecord(
        framework=case.framework,
        action_family=case.action_family.value,
        agent_service_subtype=(
            case.agent_service_subtype.value if case.agent_service_subtype is not None else None
        ),
        selected_logical_action=case.logical_action_name,
        arguments=case.argument_schema.validate_values(case.arguments),
        provider_visible_logical_request=outcome.provider_visible_logical_request,
        effect_count=outcome.effect_count,
        operation_outcome_semantics=outcome.outcome_semantics,
        result=outcome.result,
        final_framework_visible_result_state={
            "final_output": final_output,
            "action_result_received": framework_result_received,
            "action_result": outcome.result,
        },
        runtime_evidence={**evidence, "action_implementation_evidence": outcome.evidence},
    )


async def _run_openai_tool(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    from agents import Agent, RunConfig, Runner, function_tool
    from agents.items import ToolCallOutputItem
    from agents.testing import ScriptedModel

    boundary: list[tuple[str, Any]] = []
    function = _make_structured_function(case, implementation, boundary)
    registered = function_tool(function, name_override=case.logical_action_name)
    final_text = f"framework-completed:{case.case_id}"
    model = ScriptedModel(
        [
            [_openai_call(case.logical_action_name, case.arguments, case.operation_id)],
            [_openai_final(final_text)],
        ]
    )
    agent = Agent(
        name=f"V11_{case.case_id}",
        instructions="Execute the registered development action exactly once.",
        model=model,
        tools=[registered],
    )
    result = await Runner.run(agent, "local-development-input", run_config=RunConfig(tracing_disabled=True))
    outcomes = [value for stage, value in boundary if stage == "ACTION_RESULT"]
    outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    if len(outcomes) != 1 or len(outputs) != 1:
        raise AssertionError("OpenAI structured Tool did not execute exactly once")
    outcome = outcomes[0]
    return _record(
        case,
        outcome,
        str(result.final_output),
        outputs[0] == outcome.result,
        {
            "native_framework_class": type(agent).__name__,
            "framework_wide_boundary": "FunctionTool.on_invoke_tool",
            "argument_schema": case.argument_schema.schema_id,
            "tool_output_items": outputs,
            "actual_framework_api": "agents.function_tool",
        },
    )


class _MicrosoftStructuredClient:
    def __new__(cls, case: V11ActionCase):
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
                    raise NotImplementedError("V11 structured Tool adapter is non-streaming")

                async def response():
                    from agent_framework import ChatResponse, Content, Message

                    for message in messages:
                        for content in getattr(message, "contents", []):
                            if getattr(content, "type", "") == "function_result":
                                self.observed_results.append(str(getattr(content, "result", None)))
                    if self.iteration == 0:
                        value = ChatResponse(
                            messages=Message(
                                "assistant",
                                [
                                    Content.from_function_call(
                                        call_id=case.operation_id,
                                        name=case.logical_action_name,
                                        arguments=case.arguments,
                                    )
                                ],
                            )
                        )
                    else:
                        value = ChatResponse(messages=Message("assistant", [f"framework-completed:{case.case_id}"]))
                    self.iteration += 1
                    return value

                return response()

        return Client()


async def _run_microsoft_tool(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    from agent_framework import Agent, tool

    boundary: list[tuple[str, Any]] = []
    function = _make_structured_function(case, implementation, boundary)
    registered = tool(name=case.logical_action_name, approval_mode="never_require")(function)
    client = _MicrosoftStructuredClient(case)
    agent = Agent(
        client=client,
        name=f"V11_{case.case_id}",
        instructions="Execute the registered development action exactly once.",
        tools=[registered],
    )
    result = await agent.run("local-development-input")
    outcomes = [value for stage, value in boundary if stage == "ACTION_RESULT"]
    if len(outcomes) != 1:
        raise AssertionError("Microsoft structured Tool did not execute exactly once")
    outcome = outcomes[0]
    received = any(outcome.result in value for value in client.observed_results)
    return _record(
        case,
        outcome,
        result.text,
        received,
        {
            "native_framework_class": type(agent).__name__,
            "framework_wide_boundary": "FunctionInvocationLayer",
            "argument_schema": case.argument_schema.schema_id,
            "observed_function_results": client.observed_results,
            "actual_framework_api": "agent_framework.tool",
        },
    )


async def _run_openai_agent_as_tool(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    from agents import Agent, RunConfig, Runner
    from agents.items import ToolCallOutputItem
    from agents.testing import ModelStep, ScriptedModel

    outcomes: list[V11ActionOutcome] = []

    async def child_response(_call):
        outcome = implementation(case, case.argument_schema.validate_values(case.arguments))
        outcomes.append(outcome)
        return [_openai_final(outcome.result)]

    child_model = ScriptedModel([ModelStep.respond(child_response)])
    child = Agent(name="V11ChildAgent", instructions="Return the mediated child result.", model=child_model)
    child_tool = child.as_tool(
        tool_name=case.logical_action_name,
        tool_description="Execute the private child Agent service.",
    )
    parent_final = f"framework-completed:{case.case_id}"
    parent_model = ScriptedModel(
        [
            [_openai_call(case.logical_action_name, {"input": str(next(iter(case.arguments.values())))}, case.operation_id)],
            [_openai_final(parent_final)],
        ]
    )
    parent = Agent(
        name="V11ParentAgent",
        instructions="Invoke the child Agent-as-Tool once.",
        model=parent_model,
        tools=[child_tool],
    )
    result = await Runner.run(parent, "local-development-input", run_config=RunConfig(tracing_disabled=True))
    outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    if len(outcomes) != 1 or len(outputs) != 1:
        raise AssertionError("OpenAI Agent.as_tool path did not execute exactly once")
    outcome = outcomes[0]
    return _record(
        case,
        outcome,
        str(result.final_output),
        outputs[0] == outcome.result,
        {
            "actual_framework_api": "Agent.as_tool",
            "native_agent_tool_type": type(child_tool).__name__,
            "parent_agent": type(parent).__name__,
            "child_agent": type(child).__name__,
            "child_model_calls": len(child_model.calls),
            "remote_child_executed_directly": False if "canonical" in outcome.evidence else True,
        },
    )


async def _run_openai_handoff(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    from agents import Agent, RunConfig, Runner, handoff
    from agents.items import HandoffOutputItem
    from agents.testing import ModelStep, ScriptedModel

    outcomes: list[V11ActionOutcome] = []

    async def target_response(_call):
        outcome = implementation(case, case.argument_schema.validate_values(case.arguments))
        outcomes.append(outcome)
        return [_openai_final(outcome.result)]

    target_model = ScriptedModel([ModelStep.respond(target_response)])
    target = Agent(name="V11HandoffTarget", instructions="Return the mediated handoff result.", model=target_model)
    handoff_object = handoff(target)
    source_model = ScriptedModel(
        [[_openai_call(handoff_object.tool_name, {}, case.operation_id)]]
    )
    source = Agent(
        name="V11HandoffSource",
        instructions="Handoff exactly once.",
        model=source_model,
        handoffs=[handoff_object],
    )
    result = await Runner.run(source, "local-development-input", run_config=RunConfig(tracing_disabled=True))
    handoffs = [item for item in result.new_items if isinstance(item, HandoffOutputItem)]
    if len(outcomes) != 1 or len(handoffs) != 1 or result.last_agent is not target:
        raise AssertionError("OpenAI native handoff machinery did not reach the target exactly once")
    outcome = outcomes[0]
    return _record(
        case,
        outcome,
        str(result.final_output),
        str(result.final_output) == outcome.result,
        {
            "actual_framework_api": "agents.handoff",
            "native_handoff_type": type(handoff_object).__name__,
            "handoff_boundary_reached": True,
            "source_agent": source.name,
            "target_agent": target.name,
            "last_agent_is_target": result.last_agent is target,
            "remote_target_executed_directly": False if "canonical" in outcome.evidence else True,
        },
    )


class _MicrosoftChildClient:
    def __new__(cls, case: V11ActionCase, implementation: V11Implementation):
        from agent_framework import BaseChatClient, ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream

        class Client(BaseChatClient[Any]):
            def __init__(self) -> None:
                super().__init__()
                self.outcomes: list[V11ActionOutcome] = []

            def make_outcome(self) -> V11ActionOutcome:
                if self.outcomes:
                    raise AssertionError("Microsoft child Agent executed more than once")
                value = implementation(case, case.argument_schema.validate_values(case.arguments))
                self.outcomes.append(value)
                return value

            def _inner_get_response(self, *, messages, stream: bool, options, **_kwargs):
                if not stream:
                    async def response():
                        value = self.make_outcome()
                        return ChatResponse(messages=Message("assistant", [value.result]))
                    return response()

                async def updates() -> AsyncIterable[Any]:
                    value = self.make_outcome()
                    yield ChatResponseUpdate(
                        contents=[Content.from_text(value.result)],
                        role="assistant",
                        finish_reason="stop",
                    )

                def finalize(values: Sequence[Any]):
                    return ChatResponse.from_updates(values, output_format_type=options.get("response_format"))

                return ResponseStream(updates(), finalizer=finalize)

        return Client()


async def _run_microsoft_agent_as_tool(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    from agent_framework import Agent

    child_client = _MicrosoftChildClient(case, implementation)
    child = Agent(client=child_client, name="V11MicrosoftChild", instructions="Return the mediated child result.")
    child_tool = child.as_tool(name=case.logical_action_name, arg_name="task", approval_mode="never_require")

    parent_case = V11ActionCase(
        **{
            **case.__dict__,
            "argument_schema": ArgumentSchema("microsoft-agent-tool-input", case.argument_schema.fields),
            "arguments": {case.argument_schema.fields[0].name: next(iter(case.arguments.values()))},
        }
    )
    # The native Microsoft Agent-as-Tool schema is one string named ``task``.
    from dataclasses import replace

    parent_case = replace(
        parent_case,
        argument_schema=ArgumentSchema(
            "microsoft-agent-tool-task",
            (type(case.argument_schema.fields[0])("task", "str"),),
        ),
        arguments={"task": str(next(iter(case.arguments.values())))},
        logical_action_name=child_tool.name,
    )
    client = _MicrosoftStructuredClient(parent_case)
    parent = Agent(
        client=client,
        name="V11MicrosoftParent",
        instructions="Invoke the child Agent-as-Tool once.",
        tools=[child_tool],
    )
    result = await parent.run("local-development-input")
    if len(child_client.outcomes) != 1:
        raise AssertionError("Microsoft Agent.as_tool did not invoke the child exactly once")
    outcome = child_client.outcomes[0]
    received = any(outcome.result in value for value in client.observed_results)
    return _record(
        case,
        outcome,
        result.text,
        received,
        {
            "actual_framework_api": "agent_framework.Agent.as_tool",
            "native_agent_tool_type": type(child_tool).__name__,
            "parent_agent": type(parent).__name__,
            "child_agent": type(child).__name__,
            "child_streaming_path": True,
            "remote_child_executed_directly": False if "canonical" in outcome.evidence else True,
        },
    )


def run_framework_case(case: V11ActionCase, implementation: V11Implementation) -> V11SemanticRecord:
    case.validate()
    if case.framework == "OpenAI Agents SDK":
        if case.agent_service_subtype is AgentServiceSubtype.AGENT_AS_TOOL:
            coroutine = _run_openai_agent_as_tool(case, implementation)
        elif case.agent_service_subtype is AgentServiceSubtype.HANDOFF:
            coroutine = _run_openai_handoff(case, implementation)
        else:
            coroutine = _run_openai_tool(case, implementation)
    elif case.framework == "Microsoft Agent Framework":
        if case.agent_service_subtype is AgentServiceSubtype.AGENT_AS_TOOL:
            coroutine = _run_microsoft_agent_as_tool(case, implementation)
        elif case.agent_service_subtype is AgentServiceSubtype.HANDOFF:
            raise NotImplementedError("FRAMEWORK_NATIVE_MECHANISM_ABSENT: optional orchestrations package is not in the pinned snapshot")
        else:
            coroutine = _run_microsoft_tool(case, implementation)
    else:
        raise ValueError("framework-neutral actions do not have a native Agent runner")
    return asyncio.run(coroutine)


def canonical_implementation(root: Path) -> V11Implementation:
    from .canonical import canonical_external_outcome

    counter = 0

    def execute(case: V11ActionCase, arguments: dict[str, Any]) -> V11ActionOutcome:
        nonlocal counter
        if arguments != case.argument_schema.validate_values(case.arguments):
            raise AssertionError("framework changed structured arguments before mediation")
        output = root / f"call-{counter:03d}"
        counter += 1
        value = canonical_external_outcome(case, output)
        return V11ActionOutcome(
            value.result,
            value.effect_count,
            value.outcome_semantics,
            value.provider_visible_logical_request,
            {**value.evidence, "canonical": True},
        )

    return execute


def native_implementation(case: V11ActionCase, arguments: dict[str, Any]) -> V11ActionOutcome:
    from .canonical import native_local_outcome

    if arguments != case.argument_schema.validate_values(case.arguments):
        raise AssertionError("framework changed structured arguments in native reference")
    return native_local_outcome(case)
