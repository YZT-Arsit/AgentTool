from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "SEMANTIC_HOLDOUT_V3_FREEZE.json"
DIGEST = ROOT / "SEMANTIC_HOLDOUT_V3_FREEZE_SHA256.txt"

SOURCES = {
    "oai_final": ("external_stage10/openai-agents-python/examples/basic/hello_world.py", "6-13"),
    "oai_tool": ("external_stage10/openai-agents-python/examples/basic/stream_function_call_args.py", "10-42"),
    "oai_handoff": ("external_stage10/openai-agents-python/examples/sandbox/handoffs.py", "47-94"),
    "maf_agent": ("external_stage9/agent-framework/python/packages/core/tests/core/test_agents.py", "226-237;413-421"),
}


def source(name: str) -> dict[str, str]:
    path, lines = SOURCES[name]
    return {"path": path, "lines": lines,
            "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}


def expected(*, final: str, tools=None, arguments=None, call_ids=None, results=None,
             handoffs=None, updates: list[str], model_calls: int) -> dict[str, object]:
    return {
        "selected_tools": tools or [], "tool_arguments": arguments or [],
        "tool_call_ids": call_ids or [], "tool_results": results or [],
        "handoff_targets": handoffs or [], "state_updates": updates, "effect_count": 0,
        "termination_class": "RETURN", "sanitized_final_result": final,
        "model_calls": model_calls,
    }


def final_case(case_id: str, framework: str, source_id: str, task: str, final: str):
    return {
        "case_id": case_id, "framework": framework, "source": source(source_id),
        "behavior_family": "MODEL_FINAL", "public_task": task,
        "deterministic_script": [{"actor": "root", "kind": "FINAL", "text": final}],
        "expected_projection": expected(final=final, updates=["MODEL", "RETURN"], model_calls=1),
    }


def tool_case(case_id: str, framework: str, source_id: str, task: str,
              tool: str, value: str, result: str, final: str):
    args, call_id = {"input": value}, f"call-{case_id.lower()}"
    return {
        "case_id": case_id, "framework": framework, "source": source(source_id),
        "behavior_family": "MODEL_TOOL_MODEL", "public_task": task,
        "deterministic_script": [
            {"actor": "root", "kind": "TOOL_CALL", "tool": tool, "arguments": args, "call_id": call_id},
            {"actor": "tool", "kind": "TOOL_RESULT", "tool": tool, "result": result, "call_id": call_id},
            {"actor": "root", "kind": "FINAL", "text": final},
        ],
        "expected_projection": expected(
            final=final, tools=[tool], arguments=[args], call_ids=[call_id], results=[result],
            updates=["MODEL", "TOOL_CALL", "TOOL_RESULT", "MODEL_RESUME_READY", "MODEL_RESUME", "RETURN"],
            model_calls=2,
        ),
    }


def handoff_case(case_id: str, task: str, target: str, final: str):
    return {
        "case_id": case_id, "framework": "OpenAI Agents SDK", "source": source("oai_handoff"),
        "behavior_family": "LOGICAL_HANDOFF", "public_task": task,
        "deterministic_script": [
            {"actor": "intake", "kind": "HANDOFF", "target": target, "call_id": f"handoff-{case_id.lower()}"},
            {"actor": target, "kind": "FINAL", "text": final},
        ],
        "expected_projection": expected(
            final=final, handoffs=[target], updates=["MODEL", "HANDOFF", "MODEL_RESUME", "RETURN"],
            model_calls=2,
        ),
    }


def main() -> None:
    if OUT.exists() or DIGEST.exists():
        raise FileExistsError("semantic holdout V3 is already frozen")
    cases = [
        final_case("SHV3-OAI-001", "OpenAI Agents SDK", "oai_final", "Return haiku alpha.", "haiku-alpha"),
        final_case("SHV3-OAI-002", "OpenAI Agents SDK", "oai_final", "Return haiku beta.", "haiku-beta"),
        tool_case("SHV3-OAI-003", "OpenAI Agents SDK", "oai_tool", "Write bounded file A.", "write_file", "a", "written-a", "done-a"),
        tool_case("SHV3-OAI-004", "OpenAI Agents SDK", "oai_tool", "Write bounded file B.", "write_file", "b", "written-b", "done-b"),
        handoff_case("SHV3-OAI-005", "Review packet A.", "specialist", "reviewed-a"),
        handoff_case("SHV3-OAI-006", "Review packet B.", "specialist", "reviewed-b"),
        final_case("SHV3-MAF-001", "Microsoft Agent Framework", "maf_agent", "Return alpha.", "maf-alpha"),
        final_case("SHV3-MAF-002", "Microsoft Agent Framework", "maf_agent", "Return beta.", "maf-beta"),
        tool_case("SHV3-MAF-003", "Microsoft Agent Framework", "maf_agent", "Inspect A.", "inspect", "a", "inspected-a", "done-a"),
        tool_case("SHV3-MAF-004", "Microsoft Agent Framework", "maf_agent", "Inspect B.", "inspect", "b", "inspected-b", "done-b"),
        tool_case("SHV3-MAF-005", "Microsoft Agent Framework", "maf_agent", "Lookup C.", "lookup", "c", "found-c", "done-c"),
        tool_case("SHV3-MAF-006", "Microsoft Agent Framework", "maf_agent", "Lookup D.", "lookup", "d", "found-d", "done-d"),
    ]
    payload = {
        "holdout_id": "SEMANTIC-HOLDOUT-V3-20260828", "status": "FROZEN_BEFORE_EXECUTION",
        "repository_head_at_freeze": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                               text=True).strip(),
        "case_count": len(cases), "framework_counts": {"OpenAI Agents SDK": 6, "Microsoft Agent Framework": 6},
        "tool_primary_stratum_count": 6,
        "harness_pretest": "2 development-only cases passed before this manifest was created",
        "excluded_prior_holdout_sources": "all seven SEMANTIC-HOLDOUT-V2 source files",
        "run_rule": "execute once; no tuning, replacement, or rerun after observing labels",
        "pass_rule": "native deterministic projection and compiled IR projection both exactly equal frozen expected projection",
        "cases": cases,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    DIGEST.write_text(f"{digest}  {OUT.name}\n", encoding="utf-8")
    print(json.dumps({"holdout_id": payload["holdout_id"], "cases": len(cases), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
