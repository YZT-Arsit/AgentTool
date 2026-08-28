from __future__ import annotations

import json

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from agent_control_virtualization.ir import ControlEvent, Opcode
from agent_control_virtualization.ir_v2 import (DecisionKind, ModelDecision,
                                                StateScope, ToolCall)
from agent_control_virtualization.runtime_v2 import (AgentRuntimeV2,
                                                     PrivateStateStore,
                                                     ScriptedModel, ToolBinding)
from canonical_v3.compiler import lower_single_tool_agent


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


def test_canonical_lowering_preserves_the_validated_single_tool_loop() -> None:
    compiled = compile_workload_v2(
        FrameworkWorkload("test", "OpenAI Agents SDK", "test.py",
                          [FakeAgent("Agent", [FakeTool("lookup")])]),
        900,
    )
    lowered = lower_single_tool_agent(compiled)
    capsule = lowered.capsules[900]
    assert [row.opcode for row in capsule.rows] == [
        Opcode.LLM, Opcode.TOOL, Opcode.LLM, Opcode.RETURN,
    ]
    assert [row.event for row in capsule.rows] == [
        ControlEvent.START, ControlEvent.MODEL_ACTION,
        ControlEvent.TOOL_RESULT, ControlEvent.DONE,
    ]
    assert lowered.support_stratum == "NATIVE_SINGLE_TOOL_MODEL_TOOL_MODEL"


def test_canonical_lowering_rejects_multiple_tools_without_inflating_support() -> None:
    compiled = compile_workload_v2(
        FrameworkWorkload("test", "OpenAI Agents SDK", "test.py",
                          [FakeAgent("Agent", [FakeTool("one"), FakeTool("two")])]),
        901,
    )
    try:
        lower_single_tool_agent(compiled)
    except ValueError as exc:
        assert "exactly one Tool" in str(exc)
    else:
        raise AssertionError("unvalidated multi-Tool lowering was accepted")


def test_scoped_private_state_matches_native_agent_session_subset() -> None:
    from agent_framework import AgentSession

    native = AgentSession(session_id="source-session")
    native.state["history"] = {"messages": ["one", "two"]}
    native_projection = {
        "exists": "history" in native.state,
        "value": native.state["history"],
        "missing": "permission" in native.state,
    }

    compiled = PrivateStateStore(max_entries_per_namespace=4)
    compiled.set(StateScope.SESSION_PRIVATE, "source-session", "history",
                 {"messages": ["one", "two"]})
    compiled_projection = {
        "exists": compiled.exists(StateScope.SESSION_PRIVATE, "source-session", "history"),
        "value": compiled.get(StateScope.SESSION_PRIVATE, "source-session", "history"),
        "missing": compiled.exists(StateScope.SESSION_PRIVATE, "source-session", "permission"),
    }
    assert compiled_projection == native_projection
    assert compiled.snapshot(StateScope.SESSION_PRIVATE, "source-session") == native.state


def test_private_state_scope_and_bound_are_enforced() -> None:
    store = PrivateStateStore(max_entries_per_namespace=1)
    store.set(StateScope.SESSION_PRIVATE, "session-a", "key", "session")
    store.set(StateScope.AGENT_PRIVATE, "agent-a", "key", "agent")
    assert store.get(StateScope.SESSION_PRIVATE, "session-a", "key") == "session"
    assert store.get(StateScope.AGENT_PRIVATE, "agent-a", "key") == "agent"
    try:
        store.set(StateScope.SESSION_PRIVATE, "session-a", "second", "overflow")
    except OverflowError:
        pass
    else:
        raise AssertionError("state namespace exceeded its public bound")


def test_openai_agent_as_tool_lowers_to_private_call_stack_without_public_handoff() -> None:
    from agents import Agent

    child = Agent(name="Child specialist", instructions="Return the bounded child result.")
    parent = Agent(name="Parent", instructions="Call the child.", tools=[
        child.as_tool(tool_name="child_specialist", tool_description="Bounded child call"),
    ])
    compiled = compile_workload_v2(FrameworkWorkload(
        "agent-as-tool", "OpenAI Agents SDK",
        "external_stage10/openai-agents-python/examples/agent_patterns/agents_as_tools.py",
        [parent, child],
    ), 700)
    assert compiled.audit.agent_tools == 1
    assert compiled.bundle.agents[0].agent_tool_targets == {"child_specialist": 701}
    parent_model = ScriptedModel([
        ModelDecision(DecisionKind.TOOL_CALL,
                      tool_call=ToolCall("child_specialist", {"input": "bounded task"}, "agent-call-1")),
        ModelDecision(DecisionKind.FINAL, final_text="parent:child-result"),
    ])
    child_model = ScriptedModel([ModelDecision(DecisionKind.FINAL, final_text="child-result")])
    runtime = AgentRuntimeV2(compiled.bundle, {700: parent_model, 701: child_model}, {})
    result = runtime.execute(700, "task")
    assert result.termination_class == "RETURN"
    assert result.sanitized_final_result == "parent:child-result"
    assert json.loads(result.selected_tools) == ["child_specialist"]
    assert json.loads(result.tool_call_ids) == ["agent-call-1"]
    assert json.loads(result.tool_results) == ["child-result"]
    assert json.loads(result.handoff_targets) == []
    assert [item.content for item in child_model.contexts[0]] == ["bounded task"]
    resumed = json.loads(json.loads(result.next_model_context)[0])
    assert resumed[-1] == {"role": "tool", "content": "child-result",
                           "call_id": "agent-call-1", "tool_name": "child_specialist"}
    assert any(step.state.name == "AGENT_CALL_READY" for step in runtime.private_steps)
    assert any(step.state.name == "AGENT_RETURN" for step in runtime.private_steps)
