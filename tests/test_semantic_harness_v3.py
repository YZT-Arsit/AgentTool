from __future__ import annotations

from semantic_fidelity.harness_v3 import execute_case


def expected(*, tool: str = "", result: str = "", handoff: str = "", final: str,
             model_calls: int):
    if tool:
        updates = ["MODEL", "TOOL_CALL", "TOOL_RESULT", "MODEL_RESUME_READY", "MODEL_RESUME", "RETURN"]
    elif handoff:
        updates = ["MODEL", "HANDOFF", "MODEL_RESUME", "RETURN"]
    else:
        updates = ["MODEL", "RETURN"]
    return {
        "selected_tools": [tool] if tool else [], "tool_arguments": [{"input": "x"}] if tool else [],
        "tool_call_ids": ["c1"] if tool else [], "tool_results": [result] if tool else [],
        "handoff_targets": [handoff] if handoff else [], "state_updates": updates,
        "effect_count": 0, "termination_class": "RETURN", "sanitized_final_result": final,
        "model_calls": model_calls,
    }


def test_development_harness_model_tool_model_openai() -> None:
    case = {
        "case_id": "DEV-HV3-OAI", "framework": "OpenAI Agents SDK",
        "behavior_family": "MODEL_TOOL_MODEL", "public_task": "x",
        "source": {"path": "development-only"},
        "deterministic_script": [
            {"actor": "root", "kind": "TOOL_CALL", "tool": "lookup", "arguments": {"input": "x"}, "call_id": "c1"},
            {"actor": "tool", "kind": "TOOL_RESULT", "tool": "lookup", "result": "y", "call_id": "c1"},
            {"actor": "root", "kind": "FINAL", "text": "done"},
        ],
        "expected_projection": expected(tool="lookup", result="y", final="done", model_calls=2),
    }
    result = execute_case(case, 1)
    assert result["semantic_pass"] is True


def test_development_harness_handoff_openai() -> None:
    case = {
        "case_id": "DEV-HV3-HANDOFF", "framework": "OpenAI Agents SDK",
        "behavior_family": "LOGICAL_HANDOFF", "public_task": "x",
        "source": {"path": "development-only"},
        "deterministic_script": [
            {"actor": "intake", "kind": "HANDOFF", "target": "specialist", "call_id": "h1"},
            {"actor": "specialist", "kind": "FINAL", "text": "done"},
        ],
        "expected_projection": expected(handoff="specialist", final="done", model_calls=2),
    }
    result = execute_case(case, 2)
    assert result["semantic_pass"] is True
