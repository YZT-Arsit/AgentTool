from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from enum import StrEnum

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ACTION_CELL_BYTES = 1024
ACTION_CELL_PLAIN_BYTES = ACTION_CELL_BYTES - 12 - 16


class ActionKind(StrEnum):
    NOOP = "NOOP"
    TOOL = "TOOL"
    AGENT_SERVICE = "AGENT_SERVICE"
    EXTERNAL_HTTP = "EXTERNAL_HTTP"


@dataclass(frozen=True)
class ProtectedActionIntent:
    capability: str
    protected_arguments: bytes
    session_id: str
    operation_id: str
    action_kind: ActionKind


@dataclass(frozen=True)
class ActionCellV6:
    action_kind: ActionKind
    route_handle: str
    protected_arguments: bytes
    operation_id: str
    continuation_state: bytes = b""

    def encrypt(self, key: bytes, *, public_profile: str, public_slot: int) -> bytes:
        value = {
            "kind": self.action_kind.value, "route": self.route_handle,
            "arguments": self.protected_arguments.hex(), "operation_id": self.operation_id,
            "continuation": self.continuation_state.hex(),
        }
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) + 4 > ACTION_CELL_PLAIN_BYTES:
            raise ValueError("action cell payload exceeds public bound")
        plain = struct.pack("!I", len(raw)) + raw + os.urandom(ACTION_CELL_PLAIN_BYTES - 4 - len(raw))
        nonce = os.urandom(12)
        aad = f"AgentTool|ActionCellV6|{public_profile}|{public_slot}".encode()
        cell = nonce + AESGCM(key).encrypt(nonce, plain, aad)
        if len(cell) != ACTION_CELL_BYTES:
            raise AssertionError("action cell width changed")
        return cell

    @classmethod
    def decrypt(cls, key: bytes, cell: bytes, *, public_profile: str, public_slot: int) -> "ActionCellV6":
        if len(cell) != ACTION_CELL_BYTES:
            raise ValueError("invalid action cell width")
        aad = f"AgentTool|ActionCellV6|{public_profile}|{public_slot}".encode()
        plain = AESGCM(key).decrypt(cell[:12], cell[12:], aad)
        length = struct.unpack("!I", plain[:4])[0]
        if length > ACTION_CELL_PLAIN_BYTES - 4:
            raise ValueError("invalid action cell length")
        value = json.loads(plain[4:4 + length])
        return cls(ActionKind(value["kind"]), str(value["route"]), bytes.fromhex(value["arguments"]),
                   str(value["operation_id"]), bytes.fromhex(value["continuation"]))
