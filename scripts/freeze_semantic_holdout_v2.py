from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE.json"

SOURCES = {
    "oai_usage": {
        "path": "external_stage10/openai-agents-python/examples/basic/usage_tracking.py",
        "lines": "20-42",
        "sha256": "7e7b8eab58ad1c453f8320f0348fcba677b3403b8c44793273e6eb7d85f32bcd",
    },
    "oai_forced_tool": {
        "path": "external_stage10/openai-agents-python/examples/agent_patterns/forcing_tool_use.py",
        "lines": "20-81",
        "sha256": "ae853bd4a1afdeea5bda983424612a7cf9a868ec6175bfbb64f133e7d4f702c4",
    },
    "oai_routing": {
        "path": "external_stage10/openai-agents-python/examples/agent_patterns/routing.py",
        "lines": "15-34",
        "sha256": "b9b57061f5238335743ca54137df0210fd07f146613afb3783bf2a4c5650a71b",
    },
    "oai_agent_tool": {
        "path": "external_stage10/openai-agents-python/examples/agent_patterns/agents_as_tools_structured.py",
        "lines": "11-50",
        "sha256": "85ba8781e3e8f3e598be95652f0d067fb81749a56b31d59190587826fe1cce9d",
    },
    "maf_simple": {
        "path": "external_stage9/agent-framework/python/packages/core/tests/core/test_observability.py",
        "lines": "4873-4911",
        "sha256": "b332a9e1a53e71ec74fd70c9421a506cd17d8fc0d48824fc5a899f0ef9f5738f",
    },
    "maf_tool": {
        "path": "external_stage9/agent-framework/python/packages/core/tests/core/test_function_invocation_logic.py",
        "lines": "721-771",
        "sha256": "4c261b1e0419b4790bf15d0a647697a2ad9d9756aa2ce2348f7a7ea8df7d767a",
    },
    "maf_agent_tool": {
        "path": "external_stage9/agent-framework/python/packages/core/tests/core/test_agent_hooks.py",
        "lines": "1686-1707",
        "sha256": "f5f9738a2f7448229c9ac1beb0763234c1a62bfbaf22b3b7f336b53464ede473",
    },
}


def expected(*, tools: list[str] | None = None, arguments: list[dict[str, object]] | None = None,
             call_ids: list[str] | None = None, results: list[str] | None = None,
             handoffs: list[str] | None = None, updates: list[str], final: str,
             model_calls: int, effect_count: int = 0) -> dict[str, object]:
    return {
        "selected_tools": tools or [],
        "tool_arguments": arguments or [],
        "tool_call_ids": call_ids or [],
        "tool_results": results or [],
        "handoff_targets": handoffs or [],
        "state_updates": updates,
        "effect_count": effect_count,
        "termination_class": "RETURN",
        "sanitized_final_result": final,
        "model_calls": model_calls,
    }


def final_case(case_id: str, framework: str, source: str, task: str, final: str) -> dict[str, object]:
    return {
        "case_id": case_id, "framework": framework, "source": SOURCES[source],
        "behavior_family": "MODEL_FINAL", "tool_containing": False, "public_task": task,
        "deterministic_script": [{"actor": "root", "kind": "FINAL", "text": final}],
        "expected_projection": expected(updates=["MODEL", "RETURN"], final=final, model_calls=1),
    }


def tool_case(case_id: str, framework: str, source: str, task: str, tool: str,
              arguments: dict[str, object], call_id: str, result: str, final: str) -> dict[str, object]:
    return {
        "case_id": case_id, "framework": framework, "source": SOURCES[source],
        "behavior_family": "MODEL_TOOL_MODEL", "tool_containing": True, "public_task": task,
        "deterministic_script": [
            {"actor": "root", "kind": "TOOL_CALL", "tool": tool,
             "arguments": arguments, "call_id": call_id},
            {"actor": "tool", "kind": "TOOL_RESULT", "tool": tool,
             "call_id": call_id, "result": result},
            {"actor": "root", "kind": "FINAL", "text": final},
        ],
        "expected_projection": expected(
            tools=[tool], arguments=[arguments], call_ids=[call_id], results=[result],
            updates=["MODEL", "TOOL_CALL", "TOOL_RESULT", "MODEL_RESUME_READY",
                     "MODEL_RESUME", "RETURN"], final=final, model_calls=2,
        ),
    }


def handoff_case(case_id: str, task: str, target: str, call_id: str, final: str) -> dict[str, object]:
    return {
        "case_id": case_id, "framework": "OpenAI Agents SDK", "source": SOURCES["oai_routing"],
        "behavior_family": "LOGICAL_HANDOFF", "tool_containing": False, "public_task": task,
        "deterministic_script": [
            {"actor": "triage_agent", "kind": "HANDOFF", "target": target, "call_id": call_id},
            {"actor": target, "kind": "FINAL", "text": final},
        ],
        "expected_projection": expected(
            handoffs=[target], updates=["MODEL", "HANDOFF", "MODEL_RESUME", "RETURN"],
            final=final, model_calls=2,
        ),
    }


def agent_tool_case(case_id: str, framework: str, source: str, task: str, tool: str,
                    arguments: dict[str, object], call_id: str, child_result: str,
                    final: str) -> dict[str, object]:
    return {
        "case_id": case_id, "framework": framework, "source": SOURCES[source],
        "behavior_family": "AGENT_AS_TOOL_CALL_RETURN", "tool_containing": True,
        "public_task": task,
        "deterministic_script": [
            {"actor": "parent", "kind": "CALL_AGENT", "tool": tool,
             "arguments": arguments, "call_id": call_id},
            {"actor": "child", "kind": "RETURN_AGENT", "result": child_result},
            {"actor": "parent", "kind": "FINAL", "text": final},
        ],
        "expected_projection": expected(
            tools=[tool], arguments=[arguments], call_ids=[call_id], results=[child_result],
            updates=["MODEL", "CALL_AGENT", "MODEL", "RETURN_AGENT",
                     "MODEL_RESUME_READY", "MODEL", "RETURN"],
            final=final, model_calls=3,
        ),
    }


def cases() -> list[dict[str, object]]:
    values: list[dict[str, object]] = [
        final_case("SHV2-OAI-001", "OpenAI Agents SDK", "oai_usage", "Summarize alpha.", "alpha-summary"),
        final_case("SHV2-OAI-002", "OpenAI Agents SDK", "oai_usage", "Summarize beta.", "beta-summary"),
        tool_case("SHV2-OAI-003", "OpenAI Agents SDK", "oai_usage", "Weather in Tokyo?",
                  "get_weather", {"city": "Tokyo"}, "oai-weather-003",
                  "Tokyo|14-20C|Sunny with wind.", "Tokyo is Sunny with wind."),
        tool_case("SHV2-OAI-004", "OpenAI Agents SDK", "oai_usage", "Weather in Oslo?",
                  "get_weather", {"city": "Oslo"}, "oai-weather-004",
                  "Oslo|3-8C|Clear", "Oslo is Clear."),
        tool_case("SHV2-OAI-005", "OpenAI Agents SDK", "oai_forced_tool", "Weather in Kyoto?",
                  "get_weather", {"city": "Kyoto"}, "oai-forced-005",
                  "Kyoto|14-20C|Sunny with wind", "Kyoto is Sunny with wind."),
        tool_case("SHV2-OAI-006", "OpenAI Agents SDK", "oai_forced_tool", "Weather in Lima?",
                  "get_weather", {"city": "Lima"}, "oai-forced-006",
                  "Lima|18-24C|Cloudy", "Lima is Cloudy."),
        handoff_case("SHV2-OAI-007", "Answer in French.", "french_agent", "route-007", "Bonsoir."),
        handoff_case("SHV2-OAI-008", "Answer in Spanish.", "spanish_agent", "route-008", "Buenas noches."),
        agent_tool_case("SHV2-OAI-009", "OpenAI Agents SDK", "oai_agent_tool",
                        "Translate Hola from Spanish to French.", "translate_text",
                        {"text": "Hola", "source": "Spanish", "target": "French"},
                        "agent-tool-009", "Bonjour", "Translation: Bonjour"),
        agent_tool_case("SHV2-OAI-010", "OpenAI Agents SDK", "oai_agent_tool",
                        "Translate hello from English to Italian.", "translate_text",
                        {"text": "hello", "source": "English", "target": "Italian"},
                        "agent-tool-010", "ciao", "Translation: ciao"),
        tool_case("SHV2-OAI-011", "OpenAI Agents SDK", "oai_usage", "Weather in Seoul?",
                  "get_weather", {"city": "Seoul"}, "oai-weather-011",
                  "Seoul|9-15C|Rain", "Seoul is Rain."),
        tool_case("SHV2-OAI-012", "OpenAI Agents SDK", "oai_forced_tool", "Weather in Tunis?",
                  "get_weather", {"city": "Tunis"}, "oai-forced-012",
                  "Tunis|17-23C|Wind", "Tunis is Wind."),
        final_case("SHV2-MAF-001", "Microsoft Agent Framework", "maf_simple", "Return gamma.", "gamma-final"),
        final_case("SHV2-MAF-002", "Microsoft Agent Framework", "maf_simple", "Return delta.", "delta-final"),
        tool_case("SHV2-MAF-003", "Microsoft Agent Framework", "maf_tool", "Investigate issue 3.",
                  "start_todo_investigation", {"user_query": "issue-3"}, "maf-tool-003",
                  "Investigated issue-3", "done-3"),
        tool_case("SHV2-MAF-004", "Microsoft Agent Framework", "maf_tool", "Investigate issue 4.",
                  "start_todo_investigation", {"user_query": "issue-4"}, "maf-tool-004",
                  "Investigated issue-4", "done-4"),
        tool_case("SHV2-MAF-005", "Microsoft Agent Framework", "maf_tool", "Investigate issue 5.",
                  "start_todo_investigation", {"user_query": "issue-5"}, "maf-tool-005",
                  "Investigated issue-5", "done-5"),
        tool_case("SHV2-MAF-006", "Microsoft Agent Framework", "maf_tool", "Investigate issue 6.",
                  "start_todo_investigation", {"user_query": "issue-6"}, "maf-tool-006",
                  "Investigated issue-6", "done-6"),
        agent_tool_case("SHV2-MAF-007", "Microsoft Agent Framework", "maf_agent_tool",
                        "Delegate bounded task seven.", "sub_agent",
                        {"task": "bounded task seven"}, "maf-agent-tool-007",
                        "sub-result-seven", "parent-result-seven"),
        agent_tool_case("SHV2-MAF-008", "Microsoft Agent Framework", "maf_agent_tool",
                        "Delegate bounded task eight.", "sub_agent",
                        {"task": "bounded task eight"}, "maf-agent-tool-008",
                        "sub-result-eight", "parent-result-eight"),
    ]
    return values


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite frozen holdout: {OUTPUT}")
    values = cases()
    payload = {
        "holdout_id": "SEMANTIC-HOLDOUT-V2-20260828",
        "status": "FROZEN_BEFORE_EXECUTION",
        "repository_head_at_freeze": "2338d462a016fad3b6cc90bab2721421d1b12560",
        "source_commits": {
            "OpenAI Agents SDK": "a40ae9803e6b7a79faa246293f56adb100d5868b",
            "Microsoft Agent Framework": "af461de51da16f5cb800ff7febc0f8f96355607a",
        },
        "development_result_excluded_from_holdout": {
            "id": "IR-v2 frozen dynamic 72",
            "result": "72/72",
            "classification": "DEVELOPMENT_REGRESSION_ONLY",
            "reason": "the cases informed Tool-loop repair",
        },
        "freeze_rules": [
            "execute exactly once after implementation freeze",
            "do not remove or replace failed cases",
            "do not change deterministic scripts or pass criteria after execution",
            "do not tune compiler/runtime from holdout labels or failures",
            "native and compiled structured projections must both equal expected_projection",
            "next-model context, call/result pairing, effects, and one-physical-executor invariants are mandatory where applicable",
        ],
        "pass_criteria": {
            "case": "all expected_projection fields equal for native and compiled executions",
            "stratum": "report passed/total without dropping failures",
            "overall": "report passed/20; no text-similarity substitution",
        },
        "case_count": len(values),
        "tool_containing_count": sum(bool(item["tool_containing"]) for item in values),
        "cases": values,
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    OUTPUT.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    (ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE_SHA256.txt").write_text(
        f"{digest}  {OUTPUT.name}\n", encoding="utf-8"
    )
    print(json.dumps({"cases": len(values), "tool_cases": payload["tool_containing_count"],
                      "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
