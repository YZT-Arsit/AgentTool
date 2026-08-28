from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ACTION_SEMANTIC_HOLDOUT_V6_FREEZE.json"

SOURCES = {
    "OAI_TOOL": "external_stage10/openai-agents-python/examples/basic/tools.py",
    "OAI_AGENT": "external_stage10/openai-agents-python/examples/agent_patterns/agents_as_tools.py",
    "OAI_HTTP": "external_stage10/openai-agents-python/examples/mcp/get_all_mcp_tools_example/main.py",
    "MAF_TOOL": "external_stage9/agent-framework/python/packages/core/tests/core/test_function_invocation_logic.py",
    "MAF_AGENT": "external_stage9/agent-framework/python/packages/core/tests/core/test_as_tool_kwargs_propagation.py",
    "MAF_HTTP": "external_stage9/agent-framework/python/packages/core/tests/core/test_agents.py",
}


def source(kind: str) -> dict[str, str]:
    relative = SOURCES[kind]
    raw = (ROOT / relative).read_bytes()
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def case(case_id: str, framework: str, source_kind: str, family: str,
         action: str, argument: str, effectful: bool) -> dict[str, object]:
    operation_id = f"op-{case_id.lower()}"
    result = f"local:{action}:{argument}"
    return {
        "case_id": case_id, "framework": framework, "source": source(source_kind),
        "action_family": family, "action_name": action, "argument": argument,
        "operation_id": operation_id, "effectful": effectful,
        "expected_projection": {
            "selected_action": action, "arguments": argument, "result": result,
            "effect_count": int(effectful), "operation_id": operation_id, "outcome": "SUCCESS",
        },
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"holdout already frozen: {OUTPUT}")
    cases = [
        case("ASH6-OAI-001", "OpenAI Agents SDK", "OAI_TOOL", "TOOL", "get_weather", "synthetic-city-a", False),
        case("ASH6-OAI-002", "OpenAI Agents SDK", "OAI_TOOL", "TOOL", "get_weather", "synthetic-city-b", False),
        case("ASH6-OAI-003", "OpenAI Agents SDK", "OAI_TOOL", "TOOL_EFFECT", "save_preference", "synthetic-pref-a", True),
        case("ASH6-OAI-004", "OpenAI Agents SDK", "OAI_TOOL", "TOOL_EFFECT", "save_preference", "synthetic-pref-b", True),
        case("ASH6-OAI-005", "OpenAI Agents SDK", "OAI_AGENT", "AGENT_AS_SERVICE", "translation_agent", "synthetic-text-a", False),
        case("ASH6-OAI-006", "OpenAI Agents SDK", "OAI_AGENT", "AGENT_AS_SERVICE", "research_agent", "synthetic-query-a", False),
        case("ASH6-OAI-007", "OpenAI Agents SDK", "OAI_HTTP", "EXTERNAL_API", "catalog_lookup", "synthetic-capability-a", False),
        case("ASH6-OAI-008", "OpenAI Agents SDK", "OAI_HTTP", "EXTERNAL_API", "catalog_lookup", "synthetic-capability-b", False),
        case("ASH6-MAF-001", "Microsoft Agent Framework", "MAF_TOOL", "TOOL", "lookup", "synthetic-key-a", False),
        case("ASH6-MAF-002", "Microsoft Agent Framework", "MAF_TOOL", "TOOL", "lookup", "synthetic-key-b", False),
        case("ASH6-MAF-003", "Microsoft Agent Framework", "MAF_TOOL", "TOOL_EFFECT", "record_event", "synthetic-event-a", True),
        case("ASH6-MAF-004", "Microsoft Agent Framework", "MAF_TOOL", "TOOL_EFFECT", "record_event", "synthetic-event-b", True),
        case("ASH6-MAF-005", "Microsoft Agent Framework", "MAF_AGENT", "AGENT_AS_SERVICE", "delegate", "synthetic-task-a", False),
        case("ASH6-MAF-006", "Microsoft Agent Framework", "MAF_AGENT", "AGENT_AS_SERVICE", "delegate", "synthetic-task-b", False),
        case("ASH6-MAF-007", "Microsoft Agent Framework", "MAF_HTTP", "EXTERNAL_API", "remote_lookup", "synthetic-resource-a", False),
        case("ASH6-MAF-008", "Microsoft Agent Framework", "MAF_HTTP", "EXTERNAL_API", "remote_lookup", "synthetic-resource-b", False),
    ]
    manifest = {
        "holdout_id": "ACTION-SEMANTIC-HOLDOUT-V6-20260828",
        "status": "FROZEN_BEFORE_EXECUTION", "case_count": len(cases),
        "prior_semantic_holdout_sources_excluded": True,
        "run_rule": "execute once; no tuning or replacement after observing outcomes",
        "pass_rule": "native and V6-mediated exact projections both equal the frozen expected projection",
        "scope": "outbound action boundary only; not native reasoning-trace equivalence",
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    (ROOT / "ACTION_SEMANTIC_HOLDOUT_V6_FREEZE_SHA256.txt").write_text(digest + "\n", encoding="utf-8")
    print(digest)


if __name__ == "__main__":
    main()
