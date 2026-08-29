from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActionKind(StrEnum):
    NOOP = "NOOP"
    TOOL = "TOOL"
    AGENT_SERVICE = "AGENT_SERVICE"
    EXTERNAL_HTTP = "EXTERNAL_HTTP"


class PlacementClass(StrEnum):
    TRUSTED_MODULE_LOCAL = "TRUSTED_MODULE_LOCAL"
    CLOUD_LOCAL = "CLOUD_LOCAL"
    EXTERNAL = "EXTERNAL"


class EffectSemantics(StrEnum):
    READ_ONLY = "READ_ONLY"
    IDEMPOTENT_EFFECT = "IDEMPOTENT_EFFECT"
    NON_IDEMPOTENT_EFFECT = "NON_IDEMPOTENT_EFFECT"


@dataclass(frozen=True)
class ProtectedActionIntent:
    capability: str
    protected_arguments: bytes
    session_id: str
    operation_id: str
    action_kind: ActionKind


@dataclass(frozen=True)
class AgentDescriptorV7:
    """Authenticated private Agent-selection result.

    ``agent_service_route_handle`` belongs only to AGENT_SERVICE operations.
    It is intentionally not a generic action route.
    """

    agent_id: int
    capability_ids: tuple[str, ...]
    publisher_key_id: str
    agent_version: int
    placement: PlacementClass
    agent_service_route_handle: str | None
    allowed_tool_capabilities: tuple[str, ...]
    trust_class: str
    catalog_epoch: int

    def validated(self) -> "AgentDescriptorV7":
        if self.agent_id < 0 or self.agent_version < 0 or self.catalog_epoch < 0:
            raise ValueError("negative Agent descriptor identifier/version/epoch")
        if not self.capability_ids or not self.publisher_key_id:
            raise ValueError("Agent descriptor omits required identity metadata")
        return self


@dataclass(frozen=True)
class ActionRouteDescriptor:
    """Trusted capability-to-route record, never relay-visible plaintext."""

    capability: str
    route_handle: str
    action_kind: ActionKind
    placement: PlacementClass
    effect_semantics: EffectSemantics
    policy_id: str

    def validated(self) -> "ActionRouteDescriptor":
        if not self.capability or not self.route_handle or not self.policy_id:
            raise ValueError("action route descriptor is incomplete")
        if self.action_kind in (ActionKind.NOOP, ActionKind.AGENT_SERVICE):
            raise ValueError("action route map is only for TOOL/EXTERNAL_HTTP")
        return self


@dataclass(frozen=True)
class ResolvedAction:
    action_kind: ActionKind
    route_handle: str | None
    operation_id: str
    protected_arguments: bytes
    effect_semantics: EffectSemantics
    policy_id: str

