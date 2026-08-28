"""Trace-only L2 probe for Microsoft Agent Framework's existing approval path.

Run this module with the Stage-9 virtual environment and the unmodified cloned
core package on PYTHONPATH.  The local deterministic client and synthetic tool
are PROJECT-ADDED harness components; approval semantics are not modified.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, MutableSequence
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentSession,
    BaseChatClient,
    ChatResponse,
    Content,
    FunctionInvocationLayer,
    Message,
    ToolApprovalMiddleware,
    create_always_approve_tool_response,
    tool,
)


class DeterministicClient(FunctionInvocationLayer, BaseChatClient):
    """Local response queue; it makes no network or model calls."""

    def __init__(self) -> None:
        super().__init__(middleware=[])
        self.responses: list[ChatResponse] = []
        self.call_count = 0

    def _inner_get_response(
        self,
        *,
        messages: MutableSequence[Message],
        stream: bool,
        options: dict[str, Any],
        **kwargs: Any,
    ) -> Awaitable[ChatResponse]:
        del messages, stream, options, kwargs

        async def get() -> ChatResponse:
            self.call_count += 1
            if not self.responses:
                raise RuntimeError("deterministic response queue exhausted")
            return self.responses.pop(0)

        return get()

    def _inner_get_streaming_response(self, **kwargs: Any) -> Any:
        del kwargs
        raise NotImplementedError


def response(contents: list[Content] | list[str]) -> ChatResponse:
    return ChatResponse(messages=Message(role="assistant", contents=contents))


def call(call_id: str) -> Content:
    return Content.from_function_call(
        call_id=call_id,
        name="local_share_document",
        arguments='{"document":"synthetic_document_8","recipient":"contact_17"}',
    )


def encoded_size(value: Any) -> int:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return len(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode())


async def prepare_standing_rule(agent: Agent, client: DeterministicClient, session: AgentSession) -> None:
    client.responses = [response([call("warmup_call")])]
    first = await agent.run("warm up synthetic approval", session=session)
    request = first.user_input_requests[0]
    client.responses = [response(["warmup complete"])]
    await agent.run(create_always_approve_tool_response(request), session=session)


async def run_branch(existing_rule: bool) -> dict[str, Any]:
    effects: list[dict[str, str]] = []

    @tool(name="local_share_document", approval_mode="always_require")
    def local_share_document(document: str, recipient: str) -> str:
        effects.append({"document": document, "recipient": recipient})
        return "synthetic share complete"

    client = DeterministicClient()
    agent = Agent(client=client, tools=[local_share_document], middleware=[ToolApprovalMiddleware()])
    session = AgentSession(session_id=f"stage9-{'existing' if existing_rule else 'missing'}")
    if existing_rule:
        await prepare_standing_rule(agent, client, session)
        effects.clear()

    events: list[dict[str, Any]] = []
    client.responses = [response([call("measured_call")])]
    if existing_rule:
        client.responses.append(response(["task complete"]))
    before = client.call_count
    first = await agent.run("Share DOCUMENT_8 with CONTACT_17", session=session)
    events.append({
        "round": 1,
        "request_class": "PUBLIC_TASK",
        "response_content_types": [content.type for message in first.messages for content in message.contents],
        "client_calls": client.call_count - before,
        "serialized_bytes": encoded_size(first),
    })
    if not existing_rule:
        request = first.user_input_requests[0]
        client.responses = [response(["task complete"])]
        before = client.call_count
        second = await agent.run(create_always_approve_tool_response(request), session=session)
        events.append({
            "round": 2,
            "request_class": "LOCAL_APPROVAL_RESPONSE",
            "response_content_types": [content.type for message in second.messages for content in message.contents],
            "client_calls": client.call_count - before,
            "serialized_bytes": encoded_size(second),
        })
        final = second
    else:
        final = first
    state = session.state.get("tool_approval")
    state_dict = state.to_dict() if hasattr(state, "to_dict") else state
    return {
        "host_visible_trace": events,
        "effect_count": len(effects),
        "effect": effects[0] if effects else None,
        "final_text": final.text,
        "standing_rule_count_after": len((state_dict or {}).get("rules", [])),
    }


async def main(output: Path) -> None:
    existing = await run_branch(True)
    missing = await run_branch(False)
    payload = {
        "runtime": "Microsoft Agent Framework",
        "commit": "af461de51da16f5cb800ff7febc0f8f96355607a",
        "semantic_patches": "none",
        "private_state": "session-backed standing approval rule exists vs absent",
        "same_initial_task": True,
        "same_final_effect": existing["effect"] == missing["effect"] and existing["effect_count"] == missing["effect_count"] == 1,
        "existing_rule": existing,
        "missing_rule": missing,
        "trajectory_distinguishable": existing["host_visible_trace"] != missing["host_visible_trace"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output))
