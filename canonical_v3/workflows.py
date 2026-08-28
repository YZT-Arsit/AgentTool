from __future__ import annotations

from dataclasses import dataclass

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

    def kernel(self) -> ControlKernel:
        return ControlKernel(self.capsules, self.initial_agent_id, {
            READ_HANDLE: (7, OperationClass.READ_ONLY_TOOL),
            EFFECT_HANDLE: (8, OperationClass.EFFECTFUL_TOOL),
        })


def _capsule(agent: int, rows: list[ControlRow], name: str) -> AgentCapsule:
    return AgentCapsule(agent, agent + 100, 3, tuple(rows), f"canonical-v3:{name}")


def llm_read_tool() -> WorkflowFixture:
    rows = [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=READ_HANDLE, label="read"),
        ControlRow(Opcode.RETURN, ControlEvent.TOOL_RESULT, 2, 2, label="return"),
    ]
    return WorkflowFixture("LLM_READ_TOOL", {10: _capsule(10, rows, "llm-read")}, 10, 2, 0)


def llm_effect_tool() -> WorkflowFixture:
    rows = [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=EFFECT_HANDLE, label="effect"),
        ControlRow(Opcode.RETURN, ControlEvent.TOOL_RESULT, 2, 2, label="return"),
    ]
    return WorkflowFixture("LLM_EFFECT_TOOL", {11: _capsule(11, rows, "llm-effect")}, 11, 2, 1)


def logical_handoff() -> WorkflowFixture:
    first = _capsule(20, [ControlRow(Opcode.HANDOFF, ControlEvent.START, 0, 0,
                                    target_handle=21, label="handoff")], "handoff-a")
    second = _capsule(21, [
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.RETURN, ControlEvent.MODEL_ACTION, 1, 1, label="return"),
    ], "handoff-b")
    return WorkflowFixture("LOGICAL_HANDOFF", {20: first, 21: second}, 20, 1, 0)

