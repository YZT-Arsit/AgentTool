from __future__ import annotations

import json
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


@dataclass(frozen=True)
class PendingModelToolCall:
    name: str
    handle: int
    arguments: bytes
    call_id: str


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
    model_context: list[dict[str, object]] = field(default_factory=list)
    pending_model_tool: PendingModelToolCall | None = None
    tool_results: list[dict[str, object]] = field(default_factory=list)
    failure_class: str = ""


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
                 provider_by_handle: dict[int, tuple[int, OperationClass]] | None = None,
                 tool_name_by_handle: dict[int, str] | None = None,
                 initial_model_input: bytes = b"synthetic local task"):
        self.capsules = dict(capsules)
        self.state = KernelState(initial_agent_id)
        self.state.model_context.append({"role": "user", "content": initial_model_input.decode("utf-8")})
        self.provider_by_handle = dict(provider_by_handle or {})
        self.tool_name_by_handle = dict(tool_name_by_handle or {})
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
                available = [
                    {"name": self.tool_name_by_handle[row.target_handle], "handle": row.target_handle}
                    for row in capsule.rows
                    if row.current_state == result.next_state and row.event == ControlEvent.MODEL_ACTION
                    and row.opcode == Opcode.TOOL and row.target_handle in self.tool_name_by_handle
                ]
                payload = json.dumps({"context": self.state.model_context, "tools": available},
                                     sort_keys=True, separators=(",", ":")).encode("utf-8")
                operation_id = f"op-{self._next_operation:08d}"
            else:
                provider, operation_class = self.provider_by_handle.get(
                    result.target_handle, (7, OperationClass.READ_ONLY_TOOL))
                action = ACTION_TOOL
                call = self.state.pending_model_tool
                if call is None or call.handle != result.target_handle:
                    self.state.failure_class = "MODEL_TOOL_SELECTION_MISMATCH"
                    self.ticks.append(ControlTick(ordinal, False, "TOOL_SELECTION_ERROR", False, False))
                    return None
                payload = call.arguments
                operation_id = call.call_id
            descriptor = ActionDescriptor(action, provider, operation_id, payload, operation_class)
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
        self.state.current_state = int(self.state.pending_next_state)
        if result.status != 1:
            self.state.failure_class = {
                2: "PROVIDER_ERROR", 3: "PROVIDER_TIMEOUT", 4: "PROVIDER_CANCELLED",
            }.get(result.status, "PROVIDER_INVALID_STATUS")
            self.state.current_event = ControlEvent.ERROR
        elif self.state.pending_opcode == Opcode.LLM:
            try:
                decision = json.loads(result.payload)
                kind = decision["kind"]
                if kind == "TOOL_CALL":
                    name = str(decision["name"])
                    call_id = str(decision["call_id"])
                    handle = next(handle for handle, candidate in self.tool_name_by_handle.items()
                                  if candidate == name)
                    arguments = json.dumps(decision.get("arguments", {}), sort_keys=True,
                                           separators=(",", ":")).encode("utf-8")
                    self.state.pending_model_tool = PendingModelToolCall(name, handle, arguments, call_id)
                    self.state.model_context.append({"role": "assistant_tool_call", "name": name,
                                                     "arguments": json.loads(arguments), "call_id": call_id})
                    self.state.current_event = ControlEvent.MODEL_ACTION
                elif kind == "FINAL":
                    text = str(decision.get("text", ""))
                    self.state.model_context.append({"role": "assistant", "content": text})
                    self.state.sanitized_result = text.encode("utf-8")
                    self.state.current_event = ControlEvent.DONE
                else:
                    raise ValueError("unknown model decision")
            except (KeyError, ValueError, TypeError, StopIteration, json.JSONDecodeError):
                self.state.failure_class = "INVALID_MODEL_DECISION"
                self.state.current_event = ControlEvent.ERROR
        else:
            call = self.state.pending_model_tool
            if call is None:
                self.state.failure_class = "UNBOUND_TOOL_RESULT"
                self.state.current_event = ControlEvent.ERROR
            else:
                text = result.payload.decode("utf-8", errors="replace")
                self.state.tool_results.append({"name": call.name, "call_id": call.call_id,
                                                "result": text})
                self.state.model_context.append({"role": "tool", "name": call.name,
                                                 "call_id": call.call_id, "content": text})
                self.state.pending_model_tool = None
                self.state.current_event = ControlEvent.TOOL_RESULT
        self.state.pending_action = None
        self.state.pending_next_state = None
        self.state.pending_opcode = None
        return True
