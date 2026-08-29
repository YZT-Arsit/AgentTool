from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable


class DeliveryState(StrEnum):
    RECEIVED_ENCRYPTED_RESULT = "RECEIVED_ENCRYPTED_RESULT"
    DECAPSULATED = "DECAPSULATED"
    FRAMEWORK_DELIVERED = "FRAMEWORK_DELIVERED"


class FrameworkDeliveryDecision(StrEnum):
    DELIVER = "DELIVER"
    SUPPRESS_ALREADY_DELIVERED = "SUPPRESS_ALREADY_DELIVERED"


@dataclass(frozen=True)
class DeliveryEntry:
    operation_id: str
    state: DeliveryState


class DeliveryLedger:
    """Durable trusted-side framework-delivery deduplication ledger.

    The framework callback and durable `FRAMEWORK_DELIVERED` transition are not
    atomic. A crash between them remains an explicitly documented ambiguity.
    """

    def __init__(self, path: Path):
        self.path = path
        self._entries: dict[str, DeliveryState] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema") != "AgentTool.V8.DeliveryLedger/1":
                raise ValueError("delivery ledger schema mismatch")
            self._entries = {
                str(key): DeliveryState(value) for key, value in raw["entries"].items()
            }

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".next")
        payload = json.dumps(
            {
                "schema": "AgentTool.V8.DeliveryLedger/1",
                "entries": {key: value.value for key, value in sorted(self._entries.items())},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def record_received(self, operation_id: str) -> None:
        if not operation_id:
            raise ValueError("empty operation ID")
        self._entries.setdefault(operation_id, DeliveryState.RECEIVED_ENCRYPTED_RESULT)
        self._persist()

    def mark_decapsulated(self, operation_id: str) -> None:
        state = self._entries.get(operation_id)
        if state is None:
            raise LookupError("decapsulation without received result")
        if state is DeliveryState.FRAMEWORK_DELIVERED:
            return
        self._entries[operation_id] = DeliveryState.DECAPSULATED
        self._persist()

    def decision(self, operation_id: str) -> FrameworkDeliveryDecision:
        state = self._entries.get(operation_id)
        if state is DeliveryState.FRAMEWORK_DELIVERED:
            return FrameworkDeliveryDecision.SUPPRESS_ALREADY_DELIVERED
        if state is not DeliveryState.DECAPSULATED:
            raise RuntimeError("result is not durably decapsulated")
        return FrameworkDeliveryDecision.DELIVER

    def deliver(self, operation_id: str, callback: Callable[[], None]) -> FrameworkDeliveryDecision:
        decision = self.decision(operation_id)
        if decision is FrameworkDeliveryDecision.SUPPRESS_ALREADY_DELIVERED:
            return decision
        callback()
        # The callback is outside this file transaction. A crash before this
        # durable update can cause an application-level replay on restart.
        self._entries[operation_id] = DeliveryState.FRAMEWORK_DELIVERED
        self._persist()
        return FrameworkDeliveryDecision.DELIVER

    def state(self, operation_id: str) -> DeliveryState | None:
        return self._entries.get(operation_id)

