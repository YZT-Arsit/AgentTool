from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from agents import Agent, RunConfig, Runner, function_tool
from agents.testing import ScriptedModel


PUBLIC_TASK = "Send the approved synthetic status message."
PUBLIC_EFFECT = {
    "tool": "send_message",
    "recipient": "synthetic_contact@example.invalid",
    "body": "synthetic_stage10_status",
}


@dataclass(frozen=True)
class NativeRun:
    private_state: str
    same_initial_public_task: bool
    final_output: str
    effect_count: int
    effects: tuple[dict[str, str], ...]
    approval_persisted: bool
    host_visible_trace: tuple[dict[str, object], ...]
    runtime_invocations: int
    interruption_count: int
    elapsed_us: float


def _tool_call() -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        type="function_call",
        name="send_message",
        call_id="stage10-call-1",
        arguments=json.dumps(
            {
                "recipient": PUBLIC_EFFECT["recipient"],
                "body": PUBLIC_EFFECT["body"],
            },
            sort_keys=True,
        ),
    )


def _final_message() -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="stage10-final",
        type="message",
        role="assistant",
        content=[
            ResponseOutputText(
                text="completed",
                type="output_text",
                annotations=[],
                logprobs=[],
            )
        ],
        status="completed",
    )


async def run_native(private_state: str) -> NativeRun:
    """Exercise only the SDK's native approval and resume behavior.

    The identical unmeasured prelude creates a pending tool call.  The measured
    continuation starts with either a native approval decision already stored in
    RunState or the same RunState still unresolved.  Instrumentation records SDK
    boundary events; it does not change approval, retry, or effect semantics.
    """

    if private_state not in {"APPROVAL_PRESENT", "APPROVAL_ABSENT"}:
        raise ValueError(private_state)

    effects: list[dict[str, str]] = []

    @function_tool(name_override="send_message", needs_approval=True)
    def send_message(recipient: str, body: str) -> str:
        effect = {"tool": "send_message", "recipient": recipient, "body": body}
        effects.append(effect)
        return "synthetic_effect_committed"

    model = ScriptedModel([[_tool_call()], [_final_message()]])
    agent = Agent(name="Stage10Runtime2", model=model, tools=[send_message])
    config = RunConfig(tracing_disabled=True)

    # Identical setup for both private states. This is outside the measured
    # structural view and establishes the same pending public task/tool call.
    initial = await Runner.run(agent, PUBLIC_TASK, run_config=config)
    if len(initial.interruptions) != 1 or effects:
        raise AssertionError("expected one native pending approval and no effect")
    state = initial.to_state()
    approval_item = initial.interruptions[0]
    if private_state == "APPROVAL_PRESENT":
        state.approve(approval_item)

    trace: list[dict[str, object]] = []
    invocations = 0
    interruptions = 0
    started = time.perf_counter_ns()

    def record(event: str, **public: object) -> None:
        trace.append({"sequence": len(trace) + 1, "event": event, **public})

    invocations += 1
    record("MEDIATION_INVOCATION", operation="RESUME_PENDING_TOOL")
    continued = await Runner.run(agent, state, run_config=config)

    if continued.interruptions:
        interruptions += len(continued.interruptions)
        record("APPROVAL_INTERRUPTION", count=len(continued.interruptions))
        state = continued.to_state()
        # Local approval is synthetic and occurs through the SDK's public API.
        state.approve(continued.interruptions[0])
        record("LOCAL_APPROVAL_DECISION", outcome="APPROVE")
        invocations += 1
        record("MEDIATION_INVOCATION", operation="RESUME_AFTER_APPROVAL")
        continued = await Runner.run(agent, state, run_config=config)

    if continued.interruptions:
        raise AssertionError("approved continuation remained interrupted")
    if len(effects) != 1:
        raise AssertionError(f"expected one real effect, got {len(effects)}")
    record("PUBLIC_EFFECT_COMMIT", tool="send_message")
    record("SANITIZED_RESULT", result="completed")
    model.assert_complete()

    return NativeRun(
        private_state=private_state,
        same_initial_public_task=True,
        final_output=str(continued.final_output),
        effect_count=len(effects),
        effects=tuple(effects),
        approval_persisted=True,
        host_visible_trace=tuple(trace),
        runtime_invocations=invocations,
        interruption_count=interruptions,
        elapsed_us=(time.perf_counter_ns() - started) / 1000,
    )


async def probe() -> dict[str, Any]:
    present = await run_native("APPROVAL_PRESENT")
    absent = await run_native("APPROVAL_ABSENT")
    private_fields = {"private_state", "approval_state", "secret", "private_label"}
    encoded_trace = json.dumps(
        [present.host_visible_trace, absent.host_visible_trace], sort_keys=True
    )
    if any(field in encoded_trace for field in private_fields):
        raise AssertionError("private ground truth appeared in native host trace")

    def public_projection(run: NativeRun) -> dict[str, Any]:
        projected = asdict(run)
        projected.pop("private_state")
        projected.pop("approval_persisted")
        return projected

    return {
        "runtime": "OpenAI Agents SDK (Python)",
        "runtime_version": "0.22.0",
        "repository": "https://github.com/openai/openai-agents-python",
        "commit": "a40ae9803e6b7a79faa246293f56adb100d5868b",
        "semantic_patches": "none",
        "initial_public_task": PUBLIC_TASK,
        "host_visible_executions": {
            "execution_0": public_projection(present),
            "execution_1": public_projection(absent),
        },
        "private_ground_truth": {
            "execution_0": "APPROVAL_PRESENT",
            "execution_1": "APPROVAL_ABSENT",
        },
        "trusted_functional_semantics": {
            "execution_0": {"final_approval_persisted": present.approval_persisted},
            "execution_1": {"final_approval_persisted": absent.approval_persisted},
        },
        "same_initial_task": present.same_initial_public_task
        and absent.same_initial_public_task,
        "same_final_effect": present.effects == absent.effects,
        "same_effect_count": present.effect_count == absent.effect_count == 1,
        "same_sanitized_result": present.final_output == absent.final_output == "completed",
        "trajectory_distinguishable": present.host_visible_trace
        != absent.host_visible_trace,
        "instrumentation": [
            "Runner.run boundary hook",
            "interruption count hook",
            "synthetic local approval event hook",
            "synthetic effect callback hook",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(probe())
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
