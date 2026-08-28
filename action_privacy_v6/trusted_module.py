from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

from .descriptor import AgentDescriptorV6, DescriptorCodec
from .models import ActionCellV6, ProtectedActionIntent


class TrustedActionModule(Protocol):
    hardware_tee_attestation: str
    hardware_memory_confidentiality: str
    rollback_protection: str

    def capability_to_agent_id(self, capability: str) -> int | None: ...
    def recover_descriptor(self, row: bytes, expected_agent_id: int) -> AgentDescriptorV6: ...
    def make_action_cell(self, intent: ProtectedActionIntent, descriptor: AgentDescriptorV6,
                         *, public_profile: str, public_slot: int) -> bytes: ...


@dataclass(frozen=True)
class CacheDecision:
    descriptor: AgentDescriptorV6 | None
    public_pir_required: bool
    query_kind: str


class LocalTrustedBackend:
    """Functional trusted-module substitute; the local host can inspect it."""

    hardware_tee_attestation = "NOT_TESTED"
    hardware_memory_confidentiality = "NOT_TESTED"
    rollback_protection = "OPEN"

    def __init__(self, capability_index: dict[str, int], descriptor_key: bytes,
                 gateway_key: bytes, catalog_epoch: int, cache_entries: int = 32):
        self._capability_index = dict(capability_index)
        self._codec = DescriptorCodec(descriptor_key, catalog_epoch)
        self._gateway_key = gateway_key
        self._cache_entries = cache_entries
        self._cache: OrderedDict[int, AgentDescriptorV6] = OrderedDict()
        self.boot_nonce = os.urandom(32)

    @property
    def capability_index_bytes(self) -> int:
        return sum(len(key.encode()) + 8 for key in self._capability_index)

    def capability_to_agent_id(self, capability: str) -> int | None:
        return self._capability_index.get(capability)

    def recover_descriptor(self, row: bytes, expected_agent_id: int) -> AgentDescriptorV6:
        descriptor = self._codec.decode(row, expected_agent_id)
        self._cache[expected_agent_id] = descriptor
        self._cache.move_to_end(expected_agent_id)
        while len(self._cache) > self._cache_entries:
            self._cache.popitem(last=False)
        return descriptor

    def cache_decision(self, agent_id: int, *, strict: bool) -> CacheDecision:
        descriptor = self._cache.get(agent_id)
        if descriptor is not None:
            self._cache.move_to_end(agent_id)
        return CacheDecision(descriptor, strict or descriptor is None,
                             "DUMMY_ROW" if strict and descriptor is not None else "REAL_ROW")

    def make_action_cell(self, intent: ProtectedActionIntent, descriptor: AgentDescriptorV6,
                         *, public_profile: str, public_slot: int) -> bytes:
        if intent.capability not in descriptor.capability_ids:
            raise PermissionError("selected descriptor does not authorize requested capability")
        cell = ActionCellV6(intent.action_kind, descriptor.gateway_route_handle,
                            intent.protected_arguments, intent.operation_id)
        return cell.encrypt(self._gateway_key, public_profile=public_profile, public_slot=public_slot)

    def open_action_cell(self, cell: bytes, *, public_profile: str, public_slot: int) -> ActionCellV6:
        return ActionCellV6.decrypt(self._gateway_key, cell,
                                    public_profile=public_profile, public_slot=public_slot)

    def measurement(self) -> str:
        material = b"AgentTool-V6-LocalTrustedBackend|" + self.boot_nonce
        return hashlib.sha256(material).hexdigest()
