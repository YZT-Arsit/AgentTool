from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from pathlib import Path

from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir_v2 import DecisionKind, ModelDecision, ToolCall
from agent_control_virtualization.runtime_v2 import AgentRuntimeV2, ScriptedModel, ToolBinding


def _final(text: str) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id="final",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(text=text, type="output_text", annotations=[], logprobs=[])],
    )


def _call(name: str, arguments: dict[str, object], call_id: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        type="function_call",
        name=name,
        call_id=call_id,
        arguments=json.dumps(arguments, sort_keys=True),
    )


async def _native_once(seed: int) -> None:
    from agents import Agent, RunConfig, Runner, function_tool
    from agents.testing import ScriptedModel as NativeModel

    def lookup(topic: str) -> str:
        return f"faq:{topic}"

    tool = function_tool(lookup, name_override="lookup_faq")
    arguments = {"topic": f"synthetic-{seed}"}
    model = NativeModel(
        [[_call("lookup_faq", arguments, f"call-{seed}")], [_final(f"final-{seed}")]]
    )
    agent = Agent(name=f"Native{seed}", instructions="Use the local FAQ tool.", model=model, tools=[tool])
    result = await Runner.run(agent, f"task-{seed}", run_config=RunConfig(tracing_disabled=True))
    if result.final_output != f"final-{seed}" or len(model.calls) != 2:
        raise AssertionError("native framework semantic projection changed")


def _compiled_once(seed: int) -> None:
    from agents import Agent, function_tool

    def lookup(topic: str) -> str:
        return f"faq:{topic}"

    tool = function_tool(lookup, name_override="lookup_faq")
    agent = Agent(name=f"Compiled{seed}", instructions="Use the local FAQ tool.", tools=[tool])
    workload = FrameworkWorkload(
        "performance-openai-tool",
        "OpenAI Agents SDK",
        "external_stage10/openai-agents-python/examples/basic/tools.py",
        [agent],
    )
    compiled = compile_workload_v2(workload, 900_000 + seed * 10)
    agent_id = compiled.bundle.agents[0].logical_agent_id
    arguments = {"topic": f"synthetic-{seed}"}
    runtime = AgentRuntimeV2(
        compiled.bundle,
        {
            agent_id: ScriptedModel(
                [
                    ModelDecision(
                        DecisionKind.TOOL_CALL,
                        tool_call=ToolCall("lookup_faq", arguments, f"call-{seed}"),
                    ),
                    ModelDecision(DecisionKind.FINAL, final_text=f"final-{seed}"),
                ]
            )
        },
        {"lookup_faq": ToolBinding("lookup_faq", lambda values: f"faq:{values['topic']}")},
    )
    projection = runtime.execute(agent_id, f"task-{seed}")
    if projection.sanitized_final_result != f"final-{seed}" or projection.model_calls != 2:
        raise AssertionError("compiled semantic projection changed")


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()

    for seed in range(args.warmup):
        await _native_once(seed)
        _compiled_once(seed)

    measurements: dict[str, list[float]] = {"native_framework": [], "compiled_control": []}
    for seed in range(args.iterations):
        start = time.perf_counter_ns()
        await _native_once(10_000 + seed)
        measurements["native_framework"].append((time.perf_counter_ns() - start) / 1_000_000)

        start = time.perf_counter_ns()
        _compiled_once(20_000 + seed)
        measurements["compiled_control"].append((time.perf_counter_ns() - start) / 1_000_000)

    rows = []
    for component, values in measurements.items():
        rows.append(
            {
                "component": component,
                "platform": "linux",
                "workload": "source_traceable_openai_model_tool_model",
                "iterations": len(values),
                "mean_latency_ms": statistics.fmean(values),
                "p50_latency_ms": _percentile(values, 0.50),
                "p95_latency_ms": _percentile(values, 0.95),
                "min_latency_ms": min(values),
                "max_latency_ms": max(values),
                "semantic_checks": "PASS",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
