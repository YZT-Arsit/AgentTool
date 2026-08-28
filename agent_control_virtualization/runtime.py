from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Callable

from .ir import AgentCapsule, ControlEvent, Opcode, TransitionResult


@dataclass(frozen=True)
class ProtectedEvent:
    event: ControlEvent
    payload_handle: int = 0


@dataclass(frozen=True)
class ExecutionCounters:
    real_heavy_ops: int
    dummy_heavy_ops: int
    private_lookup_ops: int
    control_ops: int
    fixed_frames: int


def evaluate_transition(capsule: AgentCapsule, state: int, event: ProtectedEvent) -> TransitionResult:
    # Fixed full-row scan; this is semantic simulation, not secure computation.
    selected_opcode = Opcode.NOOP; selected_target = 0; selected_state = state; matched = 0
    for row in capsule.rows:
        is_match = int(row.current_state == state and row.event == event.event)
        matched += is_match
        if is_match:
            selected_opcode = row.opcode; selected_target = row.target_handle; selected_state = row.next_state
    return TransitionResult(selected_opcode, selected_target, selected_state, matched)


class ToolExecutionAdapter:
    public_identity = "ToolExecutionAdapter"

    def execute(self, protected_tool_handle: int, protected_args: bytes) -> bytes:
        # One representative shared heavy primitive; destination privacy beyond
        # this adapter is outside this stage.
        return hashlib.sha256(protected_tool_handle.to_bytes(4, "big") + protected_args).digest()


class AgentControlExecutor:
    public_identity = "AgentControlExecutor"

    def __init__(self, capsules: dict[int, AgentCapsule], lookup: Callable[[int], bytes] | None = None):
        self.capsules = capsules; self.lookup = lookup; self.tool_adapter = ToolExecutionAdapter()

    def step(self, logical_agent_id: int, state: int, event: ProtectedEvent) -> tuple[int, TransitionResult]:
        result = evaluate_transition(self.capsules[logical_agent_id], state, event)
        next_agent = result.target_handle if result.opcode == Opcode.HANDOFF else logical_agent_id
        return next_agent, result

    def fixed_transcript(self, logical_agent_id: int, *, rounds: int = 4,
                         frame_bytes: int = 1024, delta_ms: float = 5.0) -> tuple[dict[str, object], ...]:
        # The logical program is private audit data. The cloud sees only this
        # common executor/adapter envelope ABI. Timing is nominal only.
        return tuple({"slot": slot, "executor": self.public_identity,
                      "invocation": "PROTECTED_CONTROL_SLOT", "request_bytes": frame_bytes,
                      "response_bytes": frame_bytes,
                      "actual_request_serialized_bytes": len(serialize_fixed_envelope(slot, frame_bytes)),
                      "actual_response_serialized_bytes": len(serialize_fixed_envelope(slot, frame_bytes)),
                      "scheduled_ms": slot * delta_ms,
                      "tool_boundary": ToolExecutionAdapter.public_identity,
                      "resource_bucket": "CONTROL_1K"} for slot in range(1, rounds + 1))

    def execute_one_heavy(self, logical_agent_id: int) -> tuple[ExecutionCounters, tuple[dict[str, object], ...], float]:
        started = time.perf_counter_ns()
        # The representative path has one shared heavy call and padded control
        # slots. No NOOP invokes the model or tool.
        self.tool_adapter.execute(1, b"synthetic-protected-arguments")
        trace = self.fixed_transcript(logical_agent_id)
        return ExecutionCounters(1, 0, 1, 4, len(trace)), trace, (time.perf_counter_ns()-started)/1000


def structural_signature(trace: tuple[dict[str, object], ...]) -> str:
    return json.dumps(trace, sort_keys=True, separators=(",", ":"))


def serialize_fixed_envelope(slot: int, frame_bytes: int) -> bytes:
    """Serialize one public fixed-width frame without logical identity fields."""
    header = json.dumps({"slot": slot, "kind": "CONTROL_SLOT"}, separators=(",", ":")).encode("ascii")
    if len(header) + 1 > frame_bytes:
        raise ValueError("frame bound too small")
    return header + b"\n" + b"\0" * (frame_bytes - len(header) - 1)
