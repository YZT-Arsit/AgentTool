from __future__ import annotations

import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "external_stage9/agent-framework/python/packages/core"))
sys.path.insert(0, str(ROOT / "external_stage10/openai-agents-python/src"))

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir_v2 import DecisionKind, ModelDecision, ToolCall
from agent_control_virtualization.runtime_v2 import AgentRuntimeV2, ScriptedModel, ToolBinding

MANIFEST = ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE.json"
DIGEST_FILE = ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE_SHA256.txt"
RESULTS = ROOT / "SEMANTIC_HOLDOUT_V2_RESULTS.csv"
SUMMARY = ROOT / "SEMANTIC_HOLDOUT_V2_RESULTS.json"


class _MAFClient:
    model = "local-semantic-holdout"


def verify_freeze() -> dict[str, Any]:
    expected = DIGEST_FILE.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f"semantic holdout manifest changed: {actual} != {expected}")
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload["status"] != "FROZEN_BEFORE_EXECUTION" or payload["case_count"] != 20:
        raise RuntimeError("semantic holdout is not the frozen 20-case definition")
    for case in payload["cases"]:
        path = ROOT / case["source"]["path"]
        actual_source = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_source != case["source"]["sha256"]:
            raise RuntimeError(f"pinned source changed for {case['case_id']}")
    return payload


def decision(step: dict[str, Any]) -> ModelDecision:
    kind = step["kind"]
    if kind == "FINAL":
        return ModelDecision(DecisionKind.FINAL, final_text=step["text"])
    if kind == "TOOL_CALL":
        return ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall(
            step["tool"], step["arguments"], step["call_id"]
        ))
    if kind == "HANDOFF":
        return ModelDecision(DecisionKind.HANDOFF, handoff_target=step["target"],
                             handoff_call_id=step.get("call_id", ""))
    raise ValueError(f"not a model decision: {kind}")


def native_agents(case: dict[str, Any]) -> tuple[list[Any], str, str]:
    family = case["behavior_family"]
    script = case["deterministic_script"]
    tool_steps = [step for step in script if step["kind"] == "TOOL_CALL"]
    tool_name = tool_steps[0]["tool"] if tool_steps else ""
    if case["framework"] == "OpenAI Agents SDK":
        from agents import Agent, function_tool
        if family == "LOGICAL_HANDOFF":
            target_name = next(step["target"] for step in script if step["kind"] == "HANDOFF")
            target = Agent(name=target_name, instructions="Pinned bounded target.")
            root = Agent(name="root", instructions="Pinned bounded router.", handoffs=[target])
            return [root, target], "root", target_name
        if family == "AGENT_AS_TOOL_CALL_RETURN":
            child = Agent(name="child", instructions="Pinned bounded child.")
            root = Agent(name="root", instructions="Pinned bounded parent.", tools=[
                child.as_tool(tool_name=tool_name, tool_description="Pinned child call")
            ])
            return [root, child], "root", "child"
        if tool_name:
            def local_tool(**_: Any) -> str:
                return "uninvoked compiler object"
            local_tool.__name__ = tool_name
            tool = function_tool(local_tool, name_override=tool_name)
            return [Agent(name="root", instructions="Pinned bounded Tool flow.", tools=[tool])], "root", ""
        return [Agent(name="root", instructions="Pinned bounded final flow.")], "root", ""

    from agent_framework import Agent
    client = _MAFClient()
    if family == "AGENT_AS_TOOL_CALL_RETURN":
        child = Agent(client, name="child", instructions="Pinned bounded child.")
        root = Agent(client, name="root", instructions="Pinned bounded parent.",
                     tools=[child.as_tool(name=tool_name)])
        return [root, child], "root", "child"
    if tool_name:
        def local_tool(**_: Any) -> str:
            return "uninvoked compiler object"
        local_tool.__name__ = tool_name
        return [Agent(client, name="root", instructions="Pinned bounded Tool flow.", tools=[local_tool])], "root", ""
    return [Agent(client, name="root", instructions="Pinned bounded final flow.")], "root", ""


def execute_case(case: dict[str, Any], ordinal: int) -> dict[str, Any]:
    agents, root_name, child_name = native_agents(case)
    base = 900_000 + ordinal * 10
    workload = FrameworkWorkload(case["case_id"], case["framework"], case["source"]["path"], agents)
    compiled = compile_workload_v2(workload, base)
    ids = {agent.name: agent.logical_agent_id for agent in compiled.bundle.agents}
    scripts: dict[str, list[ModelDecision]] = {name: [] for name in ids}
    tool_results: dict[str, str] = {}
    for step in case["deterministic_script"]:
        actor = step.get("actor", "root")
        if step["kind"] in {"FINAL", "TOOL_CALL", "HANDOFF"}:
            scripts[actor].append(decision(step))
        elif step["kind"] == "TOOL_RESULT":
            tool_results[step["tool"]] = step["result"]
    models = {ids[name]: ScriptedModel(items) for name, items in scripts.items() if items}
    bindings = {name: ToolBinding(name, lambda _args, value=value: value, effectful=False)
                for name, value in tool_results.items()
                if name not in compiled.bundle.agents[0].agent_tool_targets}
    runtime = AgentRuntimeV2(compiled.bundle, models, bindings)
    projection = runtime.execute(ids[root_name], case["public_task"])
    actual = asdict(projection)
    for field in ("selected_tools", "tool_arguments", "tool_call_ids", "tool_results",
                  "handoff_targets", "state_updates"):
        actual[field] = json.loads(actual[field])
    expected = case["expected_projection"]
    mismatches = [field for field, value in expected.items() if actual[field] != value]
    return {
        "case_id": case["case_id"], "framework": case["framework"],
        "behavior_family": case["behavior_family"], "tool_containing": case["tool_containing"],
        "source_path": case["source"]["path"], "source_sha256": case["source"]["sha256"],
        "compiled_executable": compiled.audit.executable,
        "compile_unsupported_reasons": ";".join(compiled.audit.unsupported_reasons),
        "semantic_pass": not mismatches, "mismatched_fields": ";".join(mismatches),
        "expected_projection": json.dumps(expected, sort_keys=True),
        "actual_projection": json.dumps({field: actual[field] for field in expected}, sort_keys=True),
        "physical_executor": runtime.public_identity,
    }


def main() -> None:
    if RESULTS.exists() or SUMMARY.exists():
        raise FileExistsError("untouched semantic holdout has already been executed; refusing rerun")
    manifest = verify_freeze()
    rows = []
    for ordinal, case in enumerate(manifest["cases"]):
        try:
            rows.append(execute_case(case, ordinal))
        except Exception as exc:
            rows.append({
                "case_id": case["case_id"], "framework": case["framework"],
                "behavior_family": case["behavior_family"], "tool_containing": case["tool_containing"],
                "source_path": case["source"]["path"], "source_sha256": case["source"]["sha256"],
                "compiled_executable": False, "compile_unsupported_reasons": "",
                "semantic_pass": False, "mismatched_fields": "EXECUTION_ERROR",
                "expected_projection": json.dumps(case["expected_projection"], sort_keys=True),
                "actual_projection": json.dumps({"error": f"{type(exc).__name__}: {exc}"}),
                "physical_executor": "",
            })
    with RESULTS.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "holdout_id": manifest["holdout_id"], "execution_policy": "RUN_ONCE_NO_TUNING",
        "cases": len(rows), "semantic_passes": sum(bool(row["semantic_pass"]) for row in rows),
        "tool_cases": sum(bool(row["tool_containing"]) for row in rows),
        "tool_passes": sum(bool(row["tool_containing"]) and bool(row["semantic_pass"]) for row in rows),
        "by_framework": {framework: {
            "cases": sum(row["framework"] == framework for row in rows),
            "passes": sum(row["framework"] == framework and bool(row["semantic_pass"]) for row in rows),
        } for framework in sorted({row["framework"] for row in rows})},
        "failed_case_ids": [row["case_id"] for row in rows if not row["semantic_pass"]],
        "development_72_interpretation": "DEVELOPMENT_REGRESSION_ONLY",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
