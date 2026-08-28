from __future__ import annotations

import json

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir_v2 import DecisionKind, ModelDecision, ToolCall
from agent_control_virtualization.runtime_v2 import AgentRuntimeV2, ScriptedModel, ToolBinding


class FakeAgent:
    def __init__(self, name: str, tools: list[object] | None = None):
        self.name = name
        self.instructions = "bounded test instructions"
        self.tools = tools or []
        self.handoffs = []
        self.input_guardrails = []
        self.output_guardrails = []


class FakeTool:
    def __init__(self, name: str):
        self.name = name


def bundle(tools: list[str] = ["lookup"]):
    agent = FakeAgent("Agent", [FakeTool(name) for name in tools])
    return compile_workload_v2(FrameworkWorkload("test", "OpenAI Agents SDK", "test.py", [agent]), 100).bundle


def test_model_tool_model_preserves_arguments_call_id_result_and_context() -> None:
    program = bundle()
    model = ScriptedModel([
        ModelDecision(DecisionKind.TOOL_CALL,
                      tool_call=ToolCall("lookup", {"topic": "synthetic"}, "call-1")),
        ModelDecision(DecisionKind.FINAL, final_text="done"),
    ])
    runtime = AgentRuntimeV2(program, {100: model}, {
        "lookup": ToolBinding("lookup", lambda args: f"value:{args['topic']}", effectful=True),
    })
    result = runtime.execute(100, "task")
    assert json.loads(result.selected_tools) == ["lookup"]
    assert json.loads(result.tool_arguments) == [{"topic": "synthetic"}]
    assert json.loads(result.tool_call_ids) == ["call-1"]
    assert json.loads(result.tool_results) == ["value:synthetic"]
    context = json.loads(json.loads(result.next_model_context)[0])
    assert context[-2] == {"role": "assistant_tool_call", "content": '{"topic":"synthetic"}',
                           "call_id": "call-1", "tool_name": "lookup"}
    assert context[-1] == {"role": "tool", "content": "value:synthetic",
                           "call_id": "call-1", "tool_name": "lookup"}
    assert result.effect_count == 1
    assert result.model_calls == 2
    assert result.termination_class == "RETURN"
    assert result.sanitized_final_result == "done"


def test_multiple_tool_rounds_and_exactly_once_operation_id() -> None:
    program = bundle(["one", "two"])
    calls: list[str] = []
    model = ScriptedModel([
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("one", {"x": 1}, "same-id")),
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("one", {"x": 1}, "same-id")),
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("two", {"x": 2}, "other-id")),
        ModelDecision(DecisionKind.FINAL, final_text="finished"),
    ])
    runtime = AgentRuntimeV2(program, {100: model}, {
        "one": ToolBinding("one", lambda args: calls.append("one") or "one-result", effectful=True),
        "two": ToolBinding("two", lambda args: calls.append("two") or "two-result", effectful=True),
    })
    result = runtime.execute(100, "task")
    assert calls == ["one", "two"]
    assert result.effect_count == 2
    assert json.loads(result.tool_call_ids) == ["same-id", "same-id", "other-id"]
    assert result.model_calls == 4


def test_tool_error_is_private_explicit_state_and_model_can_resume() -> None:
    program = bundle()
    model = ScriptedModel([
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("lookup", {}, "bad-call")),
        ModelDecision(DecisionKind.FINAL, final_text="handled"),
    ])
    def fail(_: dict[str, object]) -> object:
        raise TimeoutError("synthetic local timeout")
    runtime = AgentRuntimeV2(program, {100: model}, {"lookup": ToolBinding("lookup", fail)})
    result = runtime.execute(100, "task")
    assert result.termination_class == "RETURN"
    assert json.loads(result.tool_results) == ["ERROR:TimeoutError"]
    assert "TOOL_ERROR" in json.loads(result.state_updates)
    assert any(step.error_class == "TimeoutError" for step in runtime.private_steps)


def test_bound_exceeded_is_explicit_and_fail_closed() -> None:
    program = compile_workload_v2(
        FrameworkWorkload("test", "OpenAI Agents SDK", "test.py", [FakeAgent("Agent", [FakeTool("loop")])]),
        100, max_model_rounds=2,
    ).bundle
    model = ScriptedModel([
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("loop", {}, "a")),
        ModelDecision(DecisionKind.TOOL_CALL, tool_call=ToolCall("loop", {}, "b")),
    ])
    runtime = AgentRuntimeV2(program, {100: model}, {"loop": ToolBinding("loop", lambda _: "again")})
    result = runtime.execute(100, "task")
    assert result.termination_class == "BOUND_EXCEEDED"
    assert result.sanitized_final_result == ""
