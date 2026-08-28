from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openai.types.responses import (ResponseFunctionToolCall,
                                    ResponseOutputMessage,
                                    ResponseOutputText)

from agent_control_virtualization.compiler import FrameworkWorkload, compile_workload
from agent_control_virtualization.ir import ControlEvent, Opcode
from agent_control_virtualization.runtime import ProtectedEvent, evaluate_transition


@dataclass(frozen=True)
class SemanticProjection:
    selected_tool: str
    tool_arguments: str
    handoff_target: str
    state_updates: str
    external_effect_sequence: str
    effect_count: int
    termination_class: str
    sanitized_final_result: str
    model_calls: int


@dataclass(frozen=True)
class FidelityRow:
    execution_id: str
    framework: str
    source_path: str
    stratum: str
    supported_static_class: bool
    equivalent: bool
    mismatched_fields: str
    native_projection: str
    compiled_projection: str


def _final(text: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(id="final", type="message", role="assistant", status="completed",
                                 content=[ResponseOutputText(text=text, type="output_text",
                                                             annotations=[], logprobs=[])])


def _call(name: str, arguments: dict[str, object], call_id: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(type="function_call", name=name, call_id=call_id,
                                    arguments=json.dumps(arguments, sort_keys=True))


def _compiled_projection(workload: FrameworkWorkload, base_id: int, scenario: str,
                         final_text: str, tool_name: str = "", tool_arguments: str = "") -> SemanticProjection:
    compiled = compile_workload(workload, base_id)
    capsules = {capsule.logical_agent_id: capsule for capsule in compiled.capsules}
    names = {base_id + index: str(getattr(agent, "name", None) or getattr(agent, "id", "agent"))
             for index, agent in enumerate(workload.agents)}
    current_agent, state, event = base_id, 0, ControlEvent.START
    updates: list[str] = []
    handoff_target = ""
    selected_tool = ""
    args = ""
    model_calls = 0
    sanitized = ""
    termination = "STALLED"
    for _ in range(16):
        result = evaluate_transition(capsules[current_agent], state, ProtectedEvent(event))
        if result.matched_rows != 1:
            updates.append("STALLED")
            break
        state = result.next_state
        updates.append(result.opcode.name)
        if result.opcode == Opcode.LLM:
            model_calls += 1
            if scenario == "tool" and model_calls == 1:
                event = ControlEvent.MODEL_ACTION
            elif scenario == "handoff" and current_agent == base_id:
                event = ControlEvent.HANDOFF_REQUEST
            else:
                sanitized = final_text
                event = ControlEvent.DONE
        elif result.opcode == Opcode.TOOL:
            selected_tool = tool_name
            # The current capsule stores only a target handle; it cannot recover
            # exact arguments, and it has no post-Tool LLM transition.
            args = ""
            event = ControlEvent.TOOL_RESULT
        elif result.opcode == Opcode.HANDOFF:
            current_agent = result.target_handle
            handoff_target = names.get(current_agent, str(current_agent))
            state, event = 0, ControlEvent.START
        elif result.opcode == Opcode.RETURN:
            termination = "RETURN"
            break
        else:
            event = ControlEvent.START
    return SemanticProjection(selected_tool, args, handoff_target, json.dumps(updates),
                              json.dumps([]), 0, termination, sanitized, model_calls)


async def _openai_simple(seed: int) -> tuple[SemanticProjection, SemanticProjection, FrameworkWorkload]:
    from agents import Agent, RunConfig, Runner
    from agents.testing import ScriptedModel
    text = f"simple-final-{seed}"
    agent = Agent(name=f"Simple{seed}", instructions="Return a deterministic answer.",
                  model=ScriptedModel([[_final(text)]]))
    result = await Runner.run(agent, f"task-{seed}", run_config=RunConfig(tracing_disabled=True))
    native = SemanticProjection("", "", "", json.dumps(["LLM", "RETURN"]), json.dumps([]),
                                0, "RETURN", str(result.final_output), 1)
    workload = FrameworkWorkload("dynamic-openai-simple", "OpenAI Agents SDK",
                                 "examples/basic/hello_world.py", [agent])
    return native, _compiled_projection(workload, 1000 + seed * 10, "simple", text), workload


async def _openai_tool(seed: int) -> tuple[SemanticProjection, SemanticProjection, FrameworkWorkload]:
    from agents import Agent, RunConfig, Runner, function_tool
    from agents.testing import ScriptedModel
    calls: list[dict[str, str]] = []

    @function_tool(name_override="lookup_faq")
    def lookup_faq(topic: str) -> str:
        calls.append({"tool": "lookup_faq", "topic": topic})
        return f"faq:{topic}"

    arguments = {"topic": f"synthetic-{seed}"}
    final_text = f"tool-final-{seed}"
    model = ScriptedModel([[_call("lookup_faq", arguments, f"call-{seed}")], [_final(final_text)]])
    agent = Agent(name=f"Tool{seed}", instructions="Use the local FAQ tool.", model=model, tools=[lookup_faq])
    result = await Runner.run(agent, f"task-{seed}", run_config=RunConfig(tracing_disabled=True))
    native = SemanticProjection("lookup_faq", json.dumps(arguments, sort_keys=True), "",
                                json.dumps(["LLM", "TOOL", "LLM", "RETURN"]),
                                json.dumps(calls, sort_keys=True), len(calls), "RETURN",
                                str(result.final_output), 2)
    workload = FrameworkWorkload("dynamic-openai-tool", "OpenAI Agents SDK",
                                 "examples/basic/tools.py", [agent])
    compiled = _compiled_projection(workload, 20_000 + seed * 10, "tool", final_text,
                                    "lookup_faq", json.dumps(arguments, sort_keys=True))
    return native, compiled, workload


async def _openai_handoff(seed: int) -> tuple[SemanticProjection, SemanticProjection, FrameworkWorkload]:
    from agents import Agent, Handoff, RunConfig, Runner
    from agents.testing import ScriptedModel
    final_text = f"handoff-final-{seed}"
    target = Agent(name=f"Specialist{seed}", instructions="Handle the task.",
                   model=ScriptedModel([[_final(final_text)]]))
    handoff_call = _call(Handoff.default_tool_name(target), {}, f"handoff-{seed}")
    start = Agent(name=f"Triage{seed}", instructions="Handoff to the specialist.",
                  model=ScriptedModel([[handoff_call]]), handoffs=[target])
    result = await Runner.run(start, f"task-{seed}", run_config=RunConfig(tracing_disabled=True))
    native = SemanticProjection("", "", target.name, json.dumps(["LLM", "HANDOFF", "LLM", "RETURN"]),
                                json.dumps([]), 0, "RETURN", str(result.final_output), 2)
    workload = FrameworkWorkload("dynamic-openai-handoff", "OpenAI Agents SDK",
                                 "examples/handoffs/message_filter.py", [start, target])
    return native, _compiled_projection(workload, 40_000 + seed * 10, "handoff", final_text), workload


class _DeterministicMicrosoftClient:
    """Local client implementing the pinned framework's documented test protocol."""
    def __init__(self, text: str):
        self.text = text
        self.call_count = 0

    def get_response(self, messages: Any, *, stream: bool = False,
                     options: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        from agent_framework import ChatResponse, Message
        async def response() -> ChatResponse:
            self.call_count += 1
            return ChatResponse(messages=Message(role="assistant", contents=[self.text]))
        return response()


async def _microsoft_simple(seed: int) -> tuple[SemanticProjection, SemanticProjection, FrameworkWorkload]:
    from agent_framework import Agent
    text = f"maf-final-{seed}"
    client = _DeterministicMicrosoftClient(text)
    agent = Agent(client=client, name=f"MAFSimple{seed}", instructions="Return a deterministic answer.")
    result = await agent.run(f"task-{seed}")
    native = SemanticProjection("", "", "", json.dumps(["LLM", "RETURN"]), json.dumps([]),
                                0, "RETURN", result.text, client.call_count)
    workload = FrameworkWorkload("dynamic-maf-simple", "Microsoft Agent Framework",
                                 "python/packages/core/tests/core/test_agents.py", [agent])
    return native, _compiled_projection(workload, 60_000 + seed * 10, "simple", text), workload


def _differences(native: SemanticProjection, compiled: SemanticProjection) -> list[str]:
    left, right = asdict(native), asdict(compiled)
    return [name for name in left if left[name] != right[name]]


async def run_dynamic_fidelity(root: Path) -> dict[str, object]:
    cases: list[tuple[str, int, Any]] = []
    cases.extend(("openai_simple", seed, _openai_simple) for seed in range(18))
    cases.extend(("openai_tool", seed, _openai_tool) for seed in range(18))
    cases.extend(("openai_handoff", seed, _openai_handoff) for seed in range(18))
    cases.extend(("microsoft_simple", seed, _microsoft_simple) for seed in range(18))
    rows: list[FidelityRow] = []
    for ordinal, (stratum, seed, runner) in enumerate(cases):
        native, compiled, workload = await runner(seed)
        differences = _differences(native, compiled)
        rows.append(FidelityRow(f"DYN-{ordinal:03d}", workload.framework, workload.source,
                                stratum, True, not differences, ";".join(differences),
                                json.dumps(asdict(native), sort_keys=True),
                                json.dumps(asdict(compiled), sort_keys=True)))
    fields = list(asdict(rows[0]))
    with (root / "SEMANTIC_FIDELITY_RESULTS.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    failures = [row for row in rows if not row.equivalent]
    with (root / "SEMANTIC_FAILURE_CASES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in failures)
    return {"executions": len(rows), "equivalent": len(rows) - len(failures),
            "failures": len(failures), "fidelity": (len(rows) - len(failures)) / len(rows),
            "by_stratum": {stratum: {
                "executions": sum(row.stratum == stratum for row in rows),
                "equivalent": sum(row.stratum == stratum and row.equivalent for row in rows),
            } for stratum in sorted({row.stratum for row in rows})}}

