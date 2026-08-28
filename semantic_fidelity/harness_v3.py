from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (
    ROOT,
    ROOT / "external_stage9/agent-framework/python/packages/core",
    ROOT / "external_stage10/openai-agents-python/src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir_v2 import DecisionKind, ModelDecision, ToolCall
from agent_control_virtualization.runtime_v2 import AgentRuntimeV2, ScriptedModel, ToolBinding


class _MAFClient:
    model = "local-semantic-harness-v3"


def _decision(step: dict[str, Any]) -> ModelDecision:
    kind = step["kind"]
    if kind == "FINAL":
        return ModelDecision(DecisionKind.FINAL, final_text=step["text"])
    if kind in {"TOOL_CALL", "CALL_AGENT"}:
        return ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall(
            step["tool"], step["arguments"], step["call_id"]
        ))
    if kind == "HANDOFF":
        return ModelDecision(DecisionKind.HANDOFF, handoff_target=step["target"],
                             handoff_call_id=step.get("call_id", ""))
    raise ValueError(f"not a model decision: {kind}")


def _named_tool(name: str):
    def local_tool(input: str) -> str:
        """Deterministic local semantic-harness Tool."""
        return input
    local_tool.__name__ = name
    return local_tool


def native_agents(case: dict[str, Any]) -> tuple[list[Any], str]:
    family = case["behavior_family"]
    script = case["deterministic_script"]
    tool_steps = [s for s in script if s["kind"] in {"TOOL_CALL", "CALL_AGENT"}]
    tool_name = tool_steps[0]["tool"] if tool_steps else ""
    if case["framework"] == "OpenAI Agents SDK":
        from agents import Agent, function_tool
        if family == "LOGICAL_HANDOFF":
            target_name = next(s["target"] for s in script if s["kind"] == "HANDOFF")
            target = Agent(name=target_name, instructions="Pinned bounded target.")
            root = Agent(name="root", instructions="Pinned bounded router.", handoffs=[target])
            return [root, target], "root"
        if family == "AGENT_AS_TOOL_CALL_RETURN":
            child = Agent(name="child", instructions="Pinned bounded child.")
            root = Agent(name="root", instructions="Pinned bounded parent.", tools=[
                child.as_tool(tool_name=tool_name, tool_description="Pinned bounded child call")
            ])
            return [root, child], "root"
        if tool_name:
            tool = function_tool(_named_tool(tool_name), name_override=tool_name)
            return [Agent(name="root", instructions="Pinned bounded Tool flow.", tools=[tool])], "root"
        return [Agent(name="root", instructions="Pinned bounded final flow.")], "root"

    from agent_framework import Agent
    if family == "AGENT_AS_TOOL_CALL_RETURN":
        child = Agent(_MAFClient(), name="child", instructions="Pinned bounded child.")
        root = Agent(_MAFClient(), name="root", instructions="Pinned bounded parent.",
                     tools=[child.as_tool(name=tool_name)])
        return [root, child], "root"
    if tool_name:
        return [Agent(_MAFClient(), name="root", instructions="Pinned bounded Tool flow.",
                      tools=[_named_tool(tool_name)])], "root"
    return [Agent(_MAFClient(), name="root", instructions="Pinned bounded final flow.")], "root"


def _canonical_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in (
        "selected_tools", "tool_arguments", "tool_call_ids", "tool_results",
        "handoff_targets", "state_updates", "effect_count", "termination_class",
        "sanitized_final_result", "model_calls",
    )}


def native_reference_projection(case: dict[str, Any], agents: list[Any]) -> dict[str, Any]:
    """Independent deterministic projection after checking native object shape.

    This intentionally does not call a network model.  It validates that the
    pinned native objects expose the referenced Tool/handoff surfaces and then
    applies the frozen deterministic model/Tool transcript as the native-side
    semantic oracle.
    """
    names = {str(getattr(agent, "name", "")) for agent in agents}
    script = case["deterministic_script"]
    selected, arguments, call_ids, results, handoffs, updates = [], [], [], [], [], []
    model_calls = 0
    final = ""
    for step in script:
        kind = step["kind"]
        if kind in {"FINAL", "TOOL_CALL", "HANDOFF", "CALL_AGENT"}:
            model_calls += 1
            updates.append("MODEL" if model_calls == 1 else "MODEL_RESUME")
        if kind == "FINAL":
            final = step["text"]; updates.append("RETURN")
        elif kind == "TOOL_CALL":
            selected.append(step["tool"]); arguments.append(step["arguments"]); call_ids.append(step["call_id"])
            updates.append("TOOL_CALL")
        elif kind == "TOOL_RESULT":
            results.append(step["result"]); updates.extend(("TOOL_RESULT", "MODEL_RESUME_READY"))
        elif kind == "HANDOFF":
            if step["target"] not in names:
                raise ValueError("frozen handoff target is absent from native Agent objects")
            handoffs.append(step["target"]); updates.append("HANDOFF")
        elif kind == "CALL_AGENT":
            if "child" not in names:
                raise ValueError("frozen Agent-as-Tool target is absent from native Agent objects")
            selected.append(step["tool"]); arguments.append(step["arguments"]); call_ids.append(step["call_id"])
            updates.append("CALL_AGENT")
        elif kind == "RETURN_AGENT":
            results.append(step["result"]); updates.extend(("RETURN_AGENT", "MODEL_RESUME_READY"))
    return {
        "selected_tools": selected, "tool_arguments": arguments, "tool_call_ids": call_ids,
        "tool_results": results, "handoff_targets": handoffs, "state_updates": updates,
        "effect_count": 0, "termination_class": "RETURN", "sanitized_final_result": final,
        "model_calls": model_calls,
    }


def execute_case(case: dict[str, Any], ordinal: int) -> dict[str, Any]:
    agents, root_name = native_agents(case)
    native = native_reference_projection(case, agents)
    compilation = compile_workload_v2(FrameworkWorkload(
        case["case_id"], case["framework"], case["source"]["path"], agents
    ), 1_500_000 + ordinal * 10)
    ids = {agent.name: agent.logical_agent_id for agent in compilation.bundle.agents}
    scripts: dict[str, list[ModelDecision]] = {name: [] for name in ids}
    tool_results: dict[str, str] = {}
    for step in case["deterministic_script"]:
        actor = step.get("actor", "root")
        if actor in {"parent", "triage_agent", "intake"}:
            actor = root_name
        if step["kind"] in {"FINAL", "TOOL_CALL", "HANDOFF", "CALL_AGENT"}:
            scripts[actor].append(_decision(step))
        elif step["kind"] == "TOOL_RESULT":
            tool_results[step["tool"]] = step["result"]
        elif step["kind"] == "RETURN_AGENT":
            scripts["child"].append(ModelDecision(DecisionKind.FINAL, final_text=step["result"]))
    models = {ids[name]: ScriptedModel(values) for name, values in scripts.items() if values}
    agent_tool_names = {name for agent in compilation.bundle.agents for name in agent.agent_tool_targets}
    tools = {name: ToolBinding(name, lambda _args, value=value: value)
             for name, value in tool_results.items() if name not in agent_tool_names}
    runtime = AgentRuntimeV2(compilation.bundle, models, tools)
    compiled_raw = asdict(runtime.execute(ids[root_name], case["public_task"]))
    for field in ("selected_tools", "tool_arguments", "tool_call_ids", "tool_results",
                  "handoff_targets", "state_updates"):
        compiled_raw[field] = json.loads(compiled_raw[field])
    compiled = _canonical_projection(compiled_raw)
    expected = case["expected_projection"]
    return {
        "native_projection": native,
        "compiled_projection": compiled,
        "expected_projection": expected,
        "native_pass": native == expected,
        "compiled_pass": compiled == expected,
        "semantic_pass": native == expected and compiled == expected,
        "compiled_executable": compilation.audit.executable,
        "unsupported_reasons": list(compilation.audit.unsupported_reasons),
        "physical_executor": runtime.public_identity,
    }
