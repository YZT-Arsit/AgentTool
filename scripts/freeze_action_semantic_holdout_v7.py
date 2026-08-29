from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ACTION_SEMANTIC_HOLDOUT_V7_FREEZE.json"

SOURCES = {
    "OAI_TOOL": "external_stage10/openai-agents-python/examples/agent_patterns/forcing_tool_use.py",
    "OAI_AGENT": "external_stage10/openai-agents-python/examples/agent_patterns/routing.py",
    "OAI_HTTP": "external_stage10/openai-agents-python/examples/mcp/streamablehttp_custom_client_example/main.py",
    "MAF_TOOL": "external_stage9/agent-framework/python/tests/samples/getting_started/test_agent_samples.py",
    "MAF_AGENT": "external_stage9/agent-framework/python/tests/samples/hosting/test_toolbox_endpoint.py",
    "MAF_HTTP": "external_stage9/agent-framework/python/tests/samples/getting_started/test_chat_client_samples.py",
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
        "case_id": case_id,
        "framework": framework,
        "source": source(source_kind),
        "action_family": family,
        "action_name": action,
        "argument": argument,
        "operation_id": operation_id,
        "effectful": effectful,
        "expected_projection": {
            "selected_action": action,
            "arguments": argument,
            "result": result,
            "effect_count": int(effectful),
            "operation_id": operation_id,
            "outcome": "SUCCESS",
        },
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"holdout already frozen: {OUTPUT}")
    definitions = [
        ("OAI", "OpenAI Agents SDK", "OAI_TOOL", "TOOL", "lookup_weather", False),
        ("OAI", "OpenAI Agents SDK", "OAI_TOOL", "TOOL_EFFECT", "persist_note", True),
        ("OAI", "OpenAI Agents SDK", "OAI_AGENT", "AGENT_AS_SERVICE", "route_specialist", False),
        ("OAI", "OpenAI Agents SDK", "OAI_HTTP", "EXTERNAL_API", "mcp_lookup", False),
        ("MAF", "Microsoft Agent Framework", "MAF_TOOL", "TOOL", "lookup_record", False),
        ("MAF", "Microsoft Agent Framework", "MAF_TOOL", "TOOL_EFFECT", "append_record", True),
        ("MAF", "Microsoft Agent Framework", "MAF_AGENT", "AGENT_AS_SERVICE", "invoke_agent_tool", False),
        ("MAF", "Microsoft Agent Framework", "MAF_HTTP", "EXTERNAL_API", "remote_query", False),
    ]
    cases = []
    ordinal = 1
    for prefix, framework, source_kind, family, action, effectful in definitions:
        for variant in range(3):
            cases.append(case(
                f"ASH7-{prefix}-{ordinal:03d}", framework, source_kind, family,
                action, f"synthetic-v7-{ordinal}-{variant}", effectful,
            ))
            ordinal += 1
    assert len(cases) == 24
    manifest = {
        "holdout_id": "ACTION-SEMANTIC-HOLDOUT-V7-20260828",
        "status": "FROZEN_BEFORE_EXECUTION",
        "case_count": len(cases),
        "v6_source_paths_excluded": True,
        "v7_implementation_guidance_excluded": True,
        "run_rule": "execute once on the authorized Linux host; no tuning, deletion, or replacement",
        "pass_rule": "native-reference and mediated exact projections both equal the frozen expected projection",
        "scope": "deterministic outbound-action adapter semantics; not full native runtime trajectory fidelity",
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    (ROOT / "ACTION_SEMANTIC_HOLDOUT_V7_FREEZE_SHA256.txt").write_text(digest + "\n", encoding="utf-8")
    print(digest)


if __name__ == "__main__":
    main()
