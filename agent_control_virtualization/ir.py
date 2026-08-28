from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import IntEnum


CAPSULE_BYTES = 1024
HEADER_BYTES = 64
ROW_BYTES = 32
MAX_ROWS = (CAPSULE_BYTES - HEADER_BYTES) // ROW_BYTES
HEADER = struct.Struct("!8sIHHII32s8s")
ROW = struct.Struct("!BBBBHHII16s")


class Opcode(IntEnum):
    NOOP = 0
    LLM = 1
    TOOL = 2
    HANDOFF = 3
    STATE_GET = 4
    STATE_SET = 5
    POLICY = 6
    RETURN = 7
    BRANCH = 8


class ControlEvent(IntEnum):
    EMPTY = 0
    START = 1
    MODEL_ACTION = 2
    TOOL_RESULT = 3
    HANDOFF_REQUEST = 4
    POLICY_RESULT = 5
    DONE = 6
    ERROR = 7


@dataclass(frozen=True)
class ControlRow:
    opcode: Opcode
    event: ControlEvent
    current_state: int
    next_state: int
    target_handle: int = 0
    auxiliary: int = 0
    flags: int = 0
    label: str = ""

    def serialize(self) -> bytes:
        digest = hashlib.blake2s(self.label.encode("utf-8"), digest_size=16).digest()
        return ROW.pack(int(self.opcode), int(self.event), self.flags, 0,
                        self.current_state, self.next_state,
                        self.target_handle, self.auxiliary, digest)


@dataclass(frozen=True)
class AgentCapsule:
    logical_agent_id: int
    instruction_handle: int
    runtime_profile: int
    rows: tuple[ControlRow, ...]
    source_digest: str

    def __post_init__(self) -> None:
        if not 0 <= self.logical_agent_id < 2**32:
            raise ValueError("logical agent id exceeds fixed ABI")
        if not 1 <= len(self.rows) <= MAX_ROWS:
            raise ValueError(f"capsule must contain 1..{MAX_ROWS} rows")
        if len({(row.current_state, row.event) for row in self.rows}) != len(self.rows):
            raise ValueError("ambiguous state/event transition")

    @property
    def state_count(self) -> int:
        return len({row.current_state for row in self.rows} | {row.next_state for row in self.rows})

    @property
    def transition_count(self) -> int:
        return len(self.rows)

    @property
    def tool_count(self) -> int:
        return sum(row.opcode == Opcode.TOOL for row in self.rows)

    @property
    def handoff_count(self) -> int:
        return sum(row.opcode == Opcode.HANDOFF for row in self.rows)

    def serialize(self) -> bytes:
        source = hashlib.sha256(self.source_digest.encode("utf-8")).digest()
        header = HEADER.pack(b"AGCTLIR1", self.logical_agent_id, len(self.rows),
                             self.runtime_profile, self.instruction_handle, 0, source, b"\0" * 8)
        body = b"".join(row.serialize() for row in self.rows)
        return header + body + b"\0" * (CAPSULE_BYTES - len(header) - len(body))

    @classmethod
    def deserialize(cls, payload: bytes) -> "AgentCapsule":
        if len(payload) != CAPSULE_BYTES:
            raise ValueError("invalid capsule width")
        magic, logical_id, row_count, profile, instruction, _, source, _ = HEADER.unpack_from(payload)
        if magic != b"AGCTLIR1" or not 1 <= row_count <= MAX_ROWS:
            raise ValueError("invalid capsule header")
        rows: list[ControlRow] = []
        for index in range(row_count):
            offset = HEADER_BYTES + index * ROW_BYTES
            opcode, event, flags, _, current, nxt, target, auxiliary, _ = ROW.unpack_from(payload, offset)
            rows.append(ControlRow(Opcode(opcode), ControlEvent(event), current, nxt,
                                   target, auxiliary, flags, "protected-row"))
        return cls(logical_id, instruction, profile, tuple(rows), source.hex())


@dataclass(frozen=True)
class TransitionResult:
    opcode: Opcode
    target_handle: int
    next_state: int
    matched_rows: int


def instruction_handle(text: str) -> int:
    return int.from_bytes(hashlib.blake2s(text.encode("utf-8"), digest_size=4).digest(), "big")


def estimate_boolean_gates(row_count: int = MAX_ROWS) -> int:
    # Per row: two fixed-width equality checks, conjunction, and masked muxes
    # for opcode/target/state. This is an engineering estimate, not a circuit.
    compare = (16 + 8) * 2
    selection = 8 + 32 + 16
    return row_count * (compare + selection) + (row_count - 1) * selection
