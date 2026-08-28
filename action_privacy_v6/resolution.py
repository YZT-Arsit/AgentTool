from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from .descriptor import AgentDescriptorV6
from .models import ProtectedActionIntent
from .trusted_module import LocalTrustedBackend


class ResolutionMode(StrEnum):
    UNIFIED_PRIVATE_REGISTRY = "UNIFIED_PRIVATE_REGISTRY"
    HIERARCHICAL_PRIVATE_RESOLUTION = "HIERARCHICAL_PRIVATE_RESOLUTION"


@dataclass(frozen=True)
class ResolutionResult:
    descriptor: AgentDescriptorV6
    public_registry: str
    public_route_class: str
    pir_queries: int
    route_leakage: str


class V6Resolver:
    def __init__(self, trusted: LocalTrustedBackend, lookup: Callable[[int], bytes],
                 *, internal_ids: frozenset[int], external_lookup: Callable[[int], bytes] | None = None):
        self._trusted = trusted
        self._lookup = lookup
        self._external_lookup = external_lookup or lookup
        self._internal_ids = internal_ids

    def resolve(self, intent: ProtectedActionIntent, mode: ResolutionMode) -> ResolutionResult:
        agent_id = self._trusted.capability_to_agent_id(intent.capability)
        if agent_id is None:
            raise LookupError("capability not present in frozen trusted catalog")
        internal = agent_id in self._internal_ids
        if mode is ResolutionMode.UNIFIED_PRIVATE_REGISTRY:
            row, registry, route, leakage = self._lookup(agent_id), "UNIFIED", "OPAQUE", "NONE"
        else:
            row = self._lookup(agent_id) if internal else self._external_lookup(agent_id)
            registry = "INTERNAL" if internal else "EXTERNAL"
            route = registry
            leakage = "INTERNAL_EXTERNAL_ROUTE_CLASS"
        descriptor = self._trusted.recover_descriptor(row, agent_id)
        return ResolutionResult(descriptor, registry, route, 1, leakage)
