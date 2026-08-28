from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from openai.types.responses import (ResponseFunctionToolCall,
                                    ResponseOutputMessage,
                                    ResponseOutputText)

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir_v2 import (ContextItem, DecisionKind,
                                                ModelDecision, ToolCall)
from agent_control_virtualization.runtime_v2 import (AgentRuntimeV2,
                                                     ExecutionProjectionV2,
                                                     ScriptedModel,
                                                     ToolBinding)
from semantic_fidelity.evaluate import _DeterministicMicrosoftClient


@dataclass(frozen=True)
class FidelityV2Row:
    execution_id: str
    seed: int
    framework: str
    source_path: str
    stratum: str
    tool_workflow: bool
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


def _context_json(items: list[ContextItem]) -> str:
    return json.dumps([item.canonical() for item in items], sort_keys=True, separators=(",", ":"))


def _normalize_native_context(items: list[dict[str, Any]]) -> str:
    normalized: list[ContextItem] = []
    call_names: dict[str, str] = {}
    for item in items:
        kind = item.get("type")
        if item.get("role") == "user":
            normalized.append(ContextItem("user", str(item.get("content", ""))))
        elif kind == "function_call":
            call_id, name = str(item["call_id"]), str(item["name"])
            call_names[call_id] = name
            arguments = json.dumps(json.loads(str(item.get("arguments", "{}"))),
                                   sort_keys=True, separators=(",", ":"))
            role = "assistant_handoff_call" if name.startswith("transfer_to_") else "assistant_tool_call"
            normalized.append(ContextItem(role, arguments, call_id, name))
        elif kind == "function_call_output":
            call_id = str(item["call_id"])
            name = call_names.get(call_id, "")
            output = str(item.get("output", ""))
            if name.startswith("transfer_to_"):
                parsed = json.loads(output)
                target = str(parsed["assistant"])
                normalized.append(ContextItem(
                    "handoff", json.dumps(parsed, sort_keys=True, separators=(",", ":")),
                    call_id, target,
                ))
            else:
                normalized.append(ContextItem("tool", output, call_id, name))
    return _context_json(normalized)


def _projection(*, selected_tools: list[str] | None = None,
                arguments: list[dict[str, object]] | None = None,
                call_ids: list[str] | None = None, results: list[str] | None = None,
                contexts: list[str] | None = None, handoffs: list[str] | None = None,
                updates: list[str], effects: list[dict[str, object]] | None = None,
                effect_count: int, final: str, model_calls: int,
                termination: str = "RETURN") -> ExecutionProjectionV2:
    return ExecutionProjectionV2(
        json.dumps(selected_tools or []), json.dumps(arguments or [], sort_keys=True),
        json.dumps(call_ids or []), json.dumps(results or []), json.dumps(contexts or []),
        json.dumps(handoffs or []), json.dumps([]), json.dumps(updates),
        json.dumps(effects or [], sort_keys=True), effect_count, termination, final, model_calls,
    )


async def _openai_simple_v2(seed: int) -> tuple[ExecutionProjectionV2, ExecutionProjectionV2, FrameworkWorkload]:
    from agents import Agent, RunConfig, Runner
    from agents.testing import ScriptedModel as NativeModel
    text, task = f"simple-final-{seed}", f"task-{seed}"
    native_model = NativeModel([[_final(text)]])
    agent = Agent(name=f"Simple{seed}", instructions="Return a deterministic answer.", model=native_model)
    result = await Runner.run(agent, task, run_config=RunConfig(tracing_disabled=True))
    native = _projection(updates=["MODEL", "RETURN"], effect_count=0,
                         final=str(result.final_output), model_calls=len(native_model.calls))
    workload = FrameworkWorkload("dynamic-openai-simple", "OpenAI Agents SDK",
                                 "examples/basic/hello_world.py", [agent])
    compiled = compile_workload_v2(workload, 1000 + seed * 10)
    agent_id = compiled.bundle.agents[0].logical_agent_id
    runtime = AgentRuntimeV2(compiled.bundle, {agent_id: ScriptedModel([
        ModelDecision(DecisionKind.FINAL, final_text=text),
    ])}, {})
    return native, runtime.execute(agent_id, task), workload


async def _openai_tool_v2(seed: int) -> tuple[ExecutionProjectionV2, ExecutionProjectionV2, FrameworkWorkload]:
    from agents import Agent, RunConfig, Runner, function_tool
    from agents.testing import ScriptedModel as NativeModel
    calls: list[dict[str, str]] = []

    def faq_impl(topic: str) -> str:
        calls.append({"tool": "lookup_faq", "topic": topic})
        return f"faq:{topic}"

    native_tool = function_tool(faq_impl, name_override="lookup_faq")
    arguments = {"topic": f"synthetic-{seed}"}
    call_id, final_text, task = f"call-{seed}", f"tool-final-{seed}", f"task-{seed}"
    native_model = NativeModel([[_call("lookup_faq", arguments, call_id)], [_final(final_text)]])
    agent = Agent(name=f"Tool{seed}", instructions="Use the local FAQ tool.",
                  model=native_model, tools=[native_tool])
    result = await Runner.run(agent, task, run_config=RunConfig(tracing_disabled=True))
    native_context = _normalize_native_context(list(native_model.calls[1].input))
    native = _projection(
        selected_tools=["lookup_faq"], arguments=[arguments], call_ids=[call_id],
        results=[f"faq:synthetic-{seed}"], contexts=[native_context],
        updates=["MODEL", "TOOL_CALL", "TOOL_RESULT", "MODEL_RESUME_READY", "MODEL_RESUME", "RETURN"],
        effects=calls, effect_count=len(calls), final=str(result.final_output), model_calls=len(native_model.calls),
    )
    workload = FrameworkWorkload("dynamic-openai-tool", "OpenAI Agents SDK",
                                 "examples/basic/tools.py", [agent])
    compiled = compile_workload_v2(workload, 20_000 + seed * 10)
    agent_id = compiled.bundle.agents[0].logical_agent_id
    compiled_calls: list[dict[str, str]] = []

    def compiled_faq(values: dict[str, object]) -> str:
        topic = str(values["topic"])
        compiled_calls.append({"tool": "lookup_faq", "topic": topic})
        return f"faq:{topic}"

    runtime = AgentRuntimeV2(
        compiled.bundle,
        {agent_id: ScriptedModel([
            ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("lookup_faq", arguments, call_id)),
            ModelDecision(DecisionKind.FINAL, final_text=final_text),
        ])},
        {"lookup_faq": ToolBinding("lookup_faq", compiled_faq, effectful=True)},
    )
    compiled_projection = runtime.execute(agent_id, task)
    if compiled_calls != calls:
        raise AssertionError("native and compiled Tool adapters observed different exact calls")
    return native, compiled_projection, workload


async def _openai_handoff_v2(seed: int) -> tuple[ExecutionProjectionV2, ExecutionProjectionV2, FrameworkWorkload]:
    from agents import Agent, Handoff, RunConfig, Runner
    from agents.testing import ScriptedModel as NativeModel
    final_text, task, call_id = f"handoff-final-{seed}", f"task-{seed}", f"handoff-{seed}"
    target_model = NativeModel([[_final(final_text)]])
    target = Agent(name=f"Specialist{seed}", instructions="Handle the task.", model=target_model)
    start_model = NativeModel([[_call(Handoff.default_tool_name(target), {}, call_id)]])
    start = Agent(name=f"Triage{seed}", instructions="Handoff to the specialist.",
                  model=start_model, handoffs=[target])
    result = await Runner.run(start, task, run_config=RunConfig(tracing_disabled=True))
    native_context = _normalize_native_context(list(target_model.calls[0].input))
    native = _projection(
        contexts=[native_context], handoffs=[target.name],
        updates=["MODEL", "HANDOFF", "MODEL_RESUME", "RETURN"], effect_count=0,
        final=str(result.final_output), model_calls=len(start_model.calls) + len(target_model.calls),
    )
    workload = FrameworkWorkload("dynamic-openai-handoff", "OpenAI Agents SDK",
                                 "examples/handoffs/message_filter.py", [start, target])
    compiled = compile_workload_v2(workload, 40_000 + seed * 10)
    start_id, target_id = (item.logical_agent_id for item in compiled.bundle.agents)
    runtime = AgentRuntimeV2(compiled.bundle, {
        start_id: ScriptedModel([ModelDecision(DecisionKind.HANDOFF,
                                               handoff_target=target.name,
                                               handoff_call_id=call_id)]),
        target_id: ScriptedModel([ModelDecision(DecisionKind.FINAL, final_text=final_text)]),
    }, {})
    return native, runtime.execute(start_id, task), workload


async def _microsoft_simple_v2(seed: int) -> tuple[ExecutionProjectionV2, ExecutionProjectionV2, FrameworkWorkload]:
    from agent_framework import Agent
    text, task = f"maf-final-{seed}", f"task-{seed}"
    client = _DeterministicMicrosoftClient(text)
    agent = Agent(client=client, name=f"MAFSimple{seed}", instructions="Return a deterministic answer.")
    result = await agent.run(task)
    native = _projection(updates=["MODEL", "RETURN"], effect_count=0,
                         final=result.text, model_calls=client.call_count)
    workload = FrameworkWorkload("dynamic-maf-simple", "Microsoft Agent Framework",
                                 "python/packages/core/tests/core/test_agents.py", [agent])
    compiled = compile_workload_v2(workload, 60_000 + seed * 10)
    agent_id = compiled.bundle.agents[0].logical_agent_id
    runtime = AgentRuntimeV2(compiled.bundle, {agent_id: ScriptedModel([
        ModelDecision(DecisionKind.FINAL, final_text=text),
    ])}, {})
    return native, runtime.execute(agent_id, task), workload


def _differences(native: ExecutionProjectionV2, compiled: ExecutionProjectionV2) -> list[str]:
    left, right = asdict(native), asdict(compiled)
    return [key for key in left if left[key] != right[key]]


async def run_frozen_72_v2(root: Path) -> dict[str, object]:
    output = root / "SEMANTIC_FIDELITY_V2_RESULTS.csv"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite IR-v2 evidence: {output}")
    cases: list[tuple[str, int, Callable[..., Any]]] = []
    cases.extend(("openai_simple", seed, _openai_simple_v2) for seed in range(18))
    cases.extend(("openai_tool", seed, _openai_tool_v2) for seed in range(18))
    cases.extend(("openai_handoff", seed, _openai_handoff_v2) for seed in range(18))
    cases.extend(("microsoft_simple", seed, _microsoft_simple_v2) for seed in range(18))
    rows: list[FidelityV2Row] = []
    for ordinal, (stratum, seed, runner) in enumerate(cases):
        native, compiled, workload = await runner(seed)
        mismatches = _differences(native, compiled)
        rows.append(FidelityV2Row(
            f"IRV2-FROZEN-{ordinal:03d}", seed, workload.framework, workload.source,
            stratum, stratum == "openai_tool", not mismatches, ";".join(mismatches),
            json.dumps(asdict(native), sort_keys=True), json.dumps(asdict(compiled), sort_keys=True),
        ))
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    return {
        "executions": len(rows),
        "equivalent": sum(row.equivalent for row in rows),
        "fidelity": sum(row.equivalent for row in rows) / len(rows),
        "tool_workflow_fidelity": sum(row.equivalent for row in rows if row.tool_workflow) /
                                  sum(row.tool_workflow for row in rows),
        "by_stratum": {stratum: {
            "executions": sum(row.stratum == stratum for row in rows),
            "equivalent": sum(row.stratum == stratum and row.equivalent for row in rows),
        } for stratum in sorted({row.stratum for row in rows})},
    }
