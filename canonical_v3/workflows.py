from __future__ import annotations

from dataclasses import dataclass, field

from agent_control_virtualization.ir import (AgentCapsule, ControlEvent,
                                             ControlRow, Opcode)
from privacy_kernel.control import ControlKernel, OperationClass


READ_HANDLE = 1001
EFFECT_HANDLE = 1002


@dataclass(frozen=True)
class WorkflowFixture:
    name: str
    capsules: dict[int, AgentCapsule]
    initial_agent_id: int
    expected_heavy_operations: int
    expected_effects: int
    provider_by_handle: dict[int, tuple[int, OperationClass]] = field(default_factory=dict)
    tool_name_by_handle: dict[int, str] = field(default_factory=dict)
    initial_private_values: dict[int, bytes] = field(default_factory=dict)

    def kernel(self) -> ControlKernel:
        providers = {
            READ_HANDLE: (7, OperationClass.READ_ONLY_TOOL),
            EFFECT_HANDLE: (8, OperationClass.EFFECTFUL_TOOL),
        }
        providers.update(self.provider_by_handle)
        names = {
            READ_HANDLE: "READ_ONLY_TOOL",
            EFFECT_HANDLE: "EFFECTFUL_TOOL",
        }
        names.update(self.tool_name_by_handle)
        kernel = ControlKernel(self.capsules, self.initial_agent_id, providers, names)
        kernel.state.private_values.update(self.initial_private_values)
        return kernel


def _capsule(agent: int, rows: list[ControlRow], name: str) -> AgentCapsule:
    return AgentCapsule(agent, agent + 100, 3, tuple(rows), f"canonical-v3:{name}")


def llm_read_tool() -> WorkflowFixture:
    rows = [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=READ_HANDLE, label="read"),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 2, 3, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 3, 3, label="return"),
    ]
    return WorkflowFixture("LLM_READ_TOOL", {10: _capsule(10, rows, "llm-read")}, 10, 3, 0)


def llm_effect_tool() -> WorkflowFixture:
    rows = [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=EFFECT_HANDLE, label="effect"),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 2, 3, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 3, 3, label="return"),
    ]
    return WorkflowFixture("LLM_EFFECT_TOOL", {11: _capsule(11, rows, "llm-effect")}, 11, 3, 1)


def logical_handoff() -> WorkflowFixture:
    first = _capsule(20, [ControlRow(Opcode.HANDOFF, ControlEvent.START, 0, 0,
                                    target_handle=21, label="handoff")], "handoff-a")
    second = _capsule(21, [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 1, 1, label="return"),
    ], "handoff-b")
    return WorkflowFixture("LOGICAL_HANDOFF", {20: first, 21: second}, 20, 1, 0)


def llm_read_tool_variant(agent_id: int, tool_handle: int, tool_name: str) -> WorkflowFixture:
    rows = [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=tool_handle, label=tool_name),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 2, 3, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 3, 3, label="return"),
    ]
    return WorkflowFixture(
        f"LLM_READ_VARIANT_{agent_id}_{tool_name}",
        {agent_id: _capsule(agent_id, rows, f"variant-{agent_id}-{tool_name}")},
        agent_id, 3, 0,
        {tool_handle: (7, OperationClass.READ_ONLY_TOOL)}, {tool_handle: tool_name},
    )


def private_branch(use_tool: bool) -> WorkflowFixture:
    state_key = 9001
    rows = [
        ControlRow(Opcode.BRANCH, ControlEvent.START, 0, 1,
                   flags=3, auxiliary=state_key, label="private-branch"),
        ControlRow(Opcode.LLM, ControlEvent.START, 1, 2, label="model-no-tool"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 2, 2, label="return-no-tool"),
        ControlRow(Opcode.LLM, ControlEvent.START, 3, 4, label="model-tool"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 4, 5,
                   target_handle=READ_HANDLE, label="branch-read"),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 5, 6, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 6, 6, label="return-tool"),
    ]
    agent_id = 31 if use_tool else 30
    return WorkflowFixture(
        f"PRIVATE_BRANCH_{'TOOL' if use_tool else 'NO_TOOL'}",
        {agent_id: _capsule(agent_id, rows, "private-branch")}, agent_id,
        3 if use_tool else 1, 0, initial_private_values={state_key: b"1"} if use_tool else {},
    )
