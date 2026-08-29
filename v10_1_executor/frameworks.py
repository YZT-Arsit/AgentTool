from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Mapping, MutableSequence, Sequence
from typing import Any

from .models import ActionImplementation, CaseSpec, FrameworkRunEvidence


def _make_action_function(case: CaseSpec, implementation: ActionImplementation, boundary: list[tuple[str, Any]]):
    """Create the exact one-string-argument ABI proven by the registry.

    Both identifiers have already passed ``str.isidentifier``.  The generated
    body is fixed; source metadata can vary names, never behavior.
    """

    def dispatch(argument: str) -> str:
        boundary.append(("ACTION_BOUNDARY", {case.argument_name: argument}))
        outcome = implementation(case, argument)
        boundary.append(("ACTION_RESULT", outcome))
        return outcome.result

    namespace: dict[str, Any] = {"_dispatch": dispatch}
    source = (
        f"def {case.logical_action_name}({case.argument_name}: str) -> str:\n"
        f"    return _dispatch({case.argument_name})\n"
    )
    exec(compile(source, "<frozen-v10.1-generic-tool-adapter>", "exec"), namespace)  # noqa: S102
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


def _openai_call(name: str, arguments: dict[str, object], call_id: str):
    from openai.types.responses import ResponseFunctionToolCall

    return ResponseFunctionToolCall(
        type="function_call", name=name, call_id=call_id, arguments=json.dumps(arguments, sort_keys=True)
    )


async def _run_openai(case: CaseSpec, implementation: ActionImplementation) -> FrameworkRunEvidence:
    from agents import Agent, RunConfig, Runner, function_tool
    from agents.items import ToolCallOutputItem
    from agents.testing import ScriptedModel

    boundary: list[tuple[str, Any]] = []

    execute_action = _make_action_function(case, implementation, boundary)
    registered_tool = function_tool(execute_action, name_override=case.logical_action_name)

    final_text = f"framework-completed:{case.case_id}"
    model = ScriptedModel(
        [[_openai_call(case.logical_action_name, {case.argument_name: case.protected_argument}, case.operation_id)], [_openai_final(final_text)]]
    )
    agent = Agent(name=f"V10_1_{case.case_id}", instructions="Execute the registered local action once.", model=model, tools=[registered_tool])
    result = await Runner.run(agent, case.prompt, run_config=RunConfig(tracing_disabled=True))
    outcomes = [value for stage, value in boundary if stage == "ACTION_RESULT"]
    tool_outputs = [str(item.output) for item in result.new_items if isinstance(item, ToolCallOutputItem)]
    if len(outcomes) != 1 or len(tool_outputs) != 1:
        raise AssertionError("OpenAI native action machinery did not execute exactly once")
    outcome = outcomes[0]
    return FrameworkRunEvidence(
        framework=case.framework,
        framework_instantiated=True,
        action_registered=len(agent.tools) == 1,
        native_action_boundary_reached=any(stage == "ACTION_BOUNDARY" for stage, _ in boundary),
        provider_request_observed=bool(outcome.provider_request),
        framework_received_result=tool_outputs[0] == outcome.result,
        selected_logical_action=case.logical_action_name,
        arguments=case.protected_argument,
        action_outcome=outcome,
        final_output=str(result.final_output),
        framework_events=("FRAMEWORK_INSTANTIATED", "ACTION_REGISTERED", "MODEL_FUNCTION_CALL", "NATIVE_ACTION_BOUNDARY", "ACTION_RESULT_RECEIVED", "FINAL_STATE"),
        runtime_evidence={"native_framework_class": type(agent).__name__, "tool_output_items": tool_outputs, "new_item_count": len(result.new_items)},
    )


class _MicrosoftToolClient:
    """Pinned MAF client with its native FunctionInvocationLayer enabled."""

    def __new__(cls, case: CaseSpec):
        from agent_framework import BaseChatClient, FunctionInvocationLayer

        class Client(FunctionInvocationLayer[Any], BaseChatClient[Any]):
            def __init__(self) -> None:
                super().__init__(middleware=[])
                self.iteration = 0
                self.observed_function_results: list[str] = []

            def _inner_get_response(
                self,
                *,
                messages: MutableSequence[Any],
                stream: bool,
                options: Mapping[str, Any],
                **_kwargs: Any,
            ) -> Awaitable[Any]:
                if stream:
                    raise NotImplementedError("V10.1 deterministic adapter is non-streaming")

                async def response():
                    from agent_framework import ChatResponse, Content, Message

                    for message in messages:
                        for content in getattr(message, "contents", []):
                            if getattr(content, "type", "") == "function_result":
                                value = getattr(content, "result", None)
                                self.observed_function_results.append(str(value))
                    if self.iteration == 0:
                        value = ChatResponse(
                            messages=Message(
                                "assistant",
                                [Content.from_function_call(call_id=case.operation_id, name=case.logical_action_name, arguments={case.argument_name: case.protected_argument})],
                            )
                        )
                    else:
                        value = ChatResponse(messages=Message("assistant", [f"framework-completed:{case.case_id}"]))
                    self.iteration += 1
                    return value

                return response()

        return Client()


async def _run_microsoft(case: CaseSpec, implementation: ActionImplementation) -> FrameworkRunEvidence:
    from agent_framework import Agent, tool

    boundary: list[tuple[str, Any]] = []

    execute_action = _make_action_function(case, implementation, boundary)
    registered_tool = tool(name=case.logical_action_name, approval_mode="never_require")(execute_action)

    client = _MicrosoftToolClient(case)
    agent = Agent(client=client, name=f"V10_1_{case.case_id}", instructions="Execute the local action once.", tools=[registered_tool])
    result = await agent.run(case.prompt)
    outcomes = [value for stage, value in boundary if stage == "ACTION_RESULT"]
    if len(outcomes) != 1:
        raise AssertionError("Microsoft native FunctionInvocationLayer did not execute exactly once")
    outcome = outcomes[0]
    received = any(outcome.result in value for value in client.observed_function_results)
    return FrameworkRunEvidence(
        framework=case.framework,
        framework_instantiated=True,
        action_registered=True,
        native_action_boundary_reached=any(stage == "ACTION_BOUNDARY" for stage, _ in boundary),
        provider_request_observed=bool(outcome.provider_request),
        framework_received_result=received,
        selected_logical_action=case.logical_action_name,
        arguments=case.protected_argument,
        action_outcome=outcome,
        final_output=result.text,
        framework_events=("FRAMEWORK_INSTANTIATED", "ACTION_REGISTERED", "MODEL_FUNCTION_CALL", "NATIVE_ACTION_BOUNDARY", "ACTION_RESULT_RECEIVED", "FINAL_STATE"),
        runtime_evidence={"native_framework_class": type(agent).__name__, "model_iterations": client.iteration, "observed_function_results": client.observed_function_results},
    )


def run_framework(case: CaseSpec, implementation: ActionImplementation) -> FrameworkRunEvidence:
    case.validate()
    coroutine = _run_openai(case, implementation) if case.framework == "OpenAI Agents SDK" else _run_microsoft(case, implementation)
    return asyncio.run(coroutine)
