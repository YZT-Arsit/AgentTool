from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, Opcode
from agent_control_virtualization.runtime import ProtectedEvent, evaluate_transition

from .protocol import ACTION_LLM, ACTION_TOOL, DecodedResult


class OperationClass(StrEnum):
    MODEL = "MODEL"
    READ_ONLY_TOOL = "READ_ONLY_TOOL"
    EFFECTFUL_TOOL = "EFFECTFUL_TOOL"


@dataclass(frozen=True)
class ActionDescriptor:
    action: int
    provider: int
    operation_id: str
    payload: bytes
    operation_class: OperationClass


@dataclass
class KernelState:
    logical_agent_id: int
    current_state: int = 0
    current_event: ControlEvent = ControlEvent.START
    pending_action: ActionDescriptor | None = None
    pending_next_state: int | None = None
    pending_opcode: Opcode | None = None
    pending_lookup: int | None = None
    pending_result: DecodedResult | None = None
    returned: bool = False
    sanitized_result: bytes = b""
    private_values: dict[int, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class ControlTick:
    tick: int
    advanced: bool
    private_opcode: str
    emitted_action: bool
    returned: bool


class ControlKernel:
    """Trusted asynchronous state machine; never executes in the Cloud Slot Proxy."""

    def __init__(self, capsules: dict[int, AgentCapsule], initial_agent_id: int,
                 provider_by_handle: dict[int, tuple[int, OperationClass]] | None = None):
        self.capsules = dict(capsules)
        self.state = KernelState(initial_agent_id)
        self.provider_by_handle = dict(provider_by_handle or {})
        self.ticks: list[ControlTick] = []
        self._next_operation = 0

    def install_capsule(self, capsule: AgentCapsule) -> None:
        self.capsules[capsule.logical_agent_id] = capsule
        if self.state.pending_lookup == capsule.logical_agent_id:
            self.state.pending_lookup = None

    def tick(self) -> ActionDescriptor | None:
        ordinal = len(self.ticks) + 1
        if self.state.returned or self.state.pending_action is not None or self.state.pending_lookup is not None:
            self.ticks.append(ControlTick(ordinal, False, "WAIT", False, self.state.returned))
            return None
        capsule = self.capsules.get(self.state.logical_agent_id)
        if capsule is None:
            self.state.pending_lookup = self.state.logical_agent_id
            self.ticks.append(ControlTick(ordinal, False, "LOOKUP_PENDING", False, False))
            return None
        result = evaluate_transition(capsule, self.state.current_state, ProtectedEvent(self.state.current_event))
        if result.matched_rows != 1:
            self.ticks.append(ControlTick(ordinal, False, "NO_MATCH", False, False))
            return None
        opcode = result.opcode
        if opcode in (Opcode.LLM, Opcode.TOOL):
            self._next_operation += 1
            if opcode == Opcode.LLM:
                provider, operation_class, action = 6, OperationClass.MODEL, ACTION_LLM
            else:
                provider, operation_class = self.provider_by_handle.get(
                    result.target_handle, (7, OperationClass.READ_ONLY_TOOL))
                action = ACTION_TOOL
            descriptor = ActionDescriptor(action, provider,
                                          f"op-{self._next_operation:08d}",
                                          result.target_handle.to_bytes(4, "big"), operation_class)
            self.state.pending_action = descriptor
            self.state.pending_next_state = result.next_state
            self.state.pending_opcode = opcode
            self.ticks.append(ControlTick(ordinal, False, opcode.name, True, False))
            return descriptor
        if opcode == Opcode.HANDOFF:
            self.state.logical_agent_id = result.target_handle
            self.state.current_state = result.next_state
            self.state.current_event = ControlEvent.START
            if result.target_handle not in self.capsules:
                self.state.pending_lookup = result.target_handle
            self.ticks.append(ControlTick(ordinal, True, opcode.name, False, False))
            return None
        if opcode == Opcode.STATE_GET:
            self.state.sanitized_result = self.state.private_values.get(result.target_handle, b"")
        elif opcode == Opcode.STATE_SET:
            self.state.private_values[result.target_handle] = result.target_handle.to_bytes(4, "big")
        elif opcode == Opcode.BRANCH:
            # Only declarative, capsule-encoded branches are accepted. Auxiliary
            # selects a private state key; flags encode the alternate state.
            row = next(row for row in capsule.rows
                       if row.current_state == self.state.current_state and row.event == self.state.current_event)
            self.state.current_state = row.flags if self.state.private_values.get(row.auxiliary) else result.next_state
            self.state.current_event = ControlEvent.START
            self.ticks.append(ControlTick(ordinal, True, opcode.name, False, False))
            return None
        elif opcode == Opcode.RETURN:
            self.state.returned = True
            self.ticks.append(ControlTick(ordinal, True, opcode.name, False, True))
            return None
        self.state.current_state = result.next_state
        self.ticks.append(ControlTick(ordinal, True, opcode.name, False, False))
        return None

    def accept_result(self, result: DecodedResult) -> bool:
        pending = self.state.pending_action
        if pending is None or result.operation_id != pending.operation_id:
            return False
        self.state.pending_result = result
        if result.status == 1:
            self.state.sanitized_result = result.payload
        self.state.current_state = int(self.state.pending_next_state)
        self.state.current_event = (ControlEvent.MODEL_ACTION
                                    if self.state.pending_opcode == Opcode.LLM
                                    else ControlEvent.TOOL_RESULT)
        self.state.pending_action = None
        self.state.pending_next_state = None
        self.state.pending_opcode = None
        return True

