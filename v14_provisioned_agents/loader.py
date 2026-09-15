from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable, Awaitable, Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Any

from .models import AgentFramework, ProvisionedAgentArtifactV1


ALLOWED_MODEL_REFERENCES = frozenset({"OAE_DETERMINISTIC_FIXTURE_V1"})
ALLOWED_CAPABILITY_REFERENCES = frozenset({"fixture.echo.v1"})


def _expected_output(artifact: ProvisionedAgentArtifactV1) -> str:
    value = artifact.runtime_policy.get("expected_output")
    if not isinstance(value, str) or not value:
        raise ValueError("artifact runtime policy lacks deterministic expected_output")
    return value


def _openai_final(text: str):
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText

    return ResponseOutputMessage(
        id="v14-final",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(text=text, type="output_text", annotations=[], logprobs=[])],
    )


def _openai_call(name: str, operation_id: str):
    from openai.types.responses import ResponseFunctionToolCall

    return ResponseFunctionToolCall(
        type="function_call",
        name=name,
        call_id=operation_id,
        arguments=json.dumps({"input": "execute nested Agent"}, sort_keys=True),
    )


def _openai_responder(text: str):
    async def respond(_call):
        return [_openai_final(text)]

    return respond


def _microsoft_static_client(text: str):
    from agent_framework import BaseChatClient, ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream

    class Client(BaseChatClient[Any]):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def _inner_get_response(self, *, messages, stream: bool, options, **_kwargs):
            self.calls += 1
            if not stream:
                async def response():
                    return ChatResponse(messages=Message("assistant", [text]))
                return response()

            async def updates() -> AsyncIterable[Any]:
                yield ChatResponseUpdate(
                    contents=[Content.from_text(text)], role="assistant", finish_reason="stop"
                )

            def finalize(values: Sequence[Any]):
                return ChatResponse.from_updates(values, output_format_type=options.get("response_format"))

            return ResponseStream(updates(), finalizer=finalize)

    return Client()


def _microsoft_tool_client(tool_name: str, final_text: str):
    from agent_framework import BaseChatClient, ChatResponse, Content, FunctionInvocationLayer, Message

    class Client(FunctionInvocationLayer[Any], BaseChatClient[Any]):
        def __init__(self) -> None:
            super().__init__(
                middleware=[],
                function_invocation_configuration={"max_iterations": 4, "max_function_calls": 2},
            )
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
                raise NotImplementedError("V14 deterministic loader uses non-streaming MAF")

            async def response():
                for message in messages:
                    for content in getattr(message, "contents", []):
                        if getattr(content, "type", "") == "function_result":
                            value = str(getattr(content, "result", None))
                            if value not in self.observed_results:
                                self.observed_results.append(value)
                if self.iteration == 0:
                    result = ChatResponse(
                        messages=Message(
                            "assistant",
                            [Content.from_function_call(
                                call_id="v14-nested-1",
                                name=tool_name,
                                arguments={"task": "execute nested Agent"},
                            )],
                        )
                    )
                else:
                    result = ChatResponse(messages=Message("assistant", [final_text]))
                self.iteration += 1
                return result

            return response()

    return Client()


@dataclass
class LoadedFrameworkAgent:
    artifact: ProvisionedAgentArtifactV1
    native_agent: object
    loaded_children: tuple["LoadedFrameworkAgent", ...]
    loader_boundary: str = "TRUSTED_RUNTIME_AGENT_LOADER"

    async def run_async(self, input_text: str = "execute") -> str:
        if self.artifact.framework is AgentFramework.OPENAI_AGENTS_SDK:
            from agents import RunConfig, Runner

            result = await Runner.run(
                self.native_agent,
                input_text,
                run_config=RunConfig(tracing_disabled=True),
            )
            return str(result.final_output)
        result = await self.native_agent.run(input_text)
        return str(result.text)

    def run(self, input_text: str = "execute") -> str:
        return asyncio.run(self.run_async(input_text))

    def evidence(self) -> dict[str, object]:
        return {
            "framework": self.artifact.framework.value,
            "native_class": type(self.native_agent).__name__,
            "agent_id": self.artifact.canonical_agent_id,
            "loader_boundary": self.loader_boundary,
            "sub_agent_ids": list(self.artifact.sub_agent_ids),
            "loaded_child_count": len(self.loaded_children),
            "remote_agent_service_invocations": 0,
            "agent_specific_gateway_destinations": 0,
        }


class AgentLoader:
    """Allowlisted construction of actual SDK Agent objects inside trust boundary."""

    def load(
        self,
        artifact: ProvisionedAgentArtifactV1,
        children: Sequence[LoadedFrameworkAgent] = (),
    ) -> LoadedFrameworkAgent:
        artifact = artifact.validated()
        if artifact.model_reference not in ALLOWED_MODEL_REFERENCES:
            raise PermissionError("artifact model reference is not allowlisted")
        if not set(artifact.tool_capability_refs).issubset(ALLOWED_CAPABILITY_REFERENCES):
            raise PermissionError("artifact capability reference is not allowlisted")
        expected_children = artifact.sub_agent_ids
        actual_children = tuple(child.artifact.canonical_agent_id for child in children)
        if actual_children != expected_children:
            raise ValueError("loaded child inventory does not match artifact references")
        if any(child.artifact.framework is not artifact.framework for child in children):
            raise ValueError("cross-framework child Agent is unsupported by V14 loader")
        output = _expected_output(artifact)

        if artifact.framework is AgentFramework.OPENAI_AGENTS_SDK:
            from agents import Agent
            from agents.testing import ModelStep, ScriptedModel

            tools = []
            if children:
                if len(children) != 1:
                    raise ValueError("OpenAI V14 fixture supports exactly one nested Agent")
                child_tool = children[0].native_agent.as_tool(
                    tool_name=f"agent_{children[0].artifact.canonical_agent_id}",
                    tool_description="Privately retrieved nested Agent",
                )
                tools.append(child_tool)
                model = ScriptedModel(
                    [[_openai_call(child_tool.name, "v14-nested-1")], [_openai_final(output)]]
                )
            else:
                model = ScriptedModel([ModelStep.respond(_openai_responder(output))])
            native = Agent(
                name=artifact.name,
                instructions=artifact.instructions,
                model=model,
                tools=tools,
            )
        else:
            from agent_framework import Agent

            tools = []
            if children:
                if len(children) != 1:
                    raise ValueError("MAF V14 fixture supports exactly one nested Agent")
                child_tool = children[0].native_agent.as_tool(
                    name=f"agent_{children[0].artifact.canonical_agent_id}",
                    arg_name="task",
                    approval_mode="never_require",
                )
                tools.append(child_tool)
                client = _microsoft_tool_client(child_tool.name, output)
            else:
                client = _microsoft_static_client(output)
            native = Agent(
                client=client,
                name=artifact.name,
                instructions=artifact.instructions,
                tools=tools,
            )
        return LoadedFrameworkAgent(artifact, native, tuple(children))
