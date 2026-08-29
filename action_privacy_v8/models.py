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


class PrivacyProfile(StrEnum):
    STRICT = "STRICT"
    CONFIDENTIAL_ENTERPRISE = "CONFIDENTIAL_ENTERPRISE"
    ENTERPRISE_EFFICIENT = "ENTERPRISE_EFFICIENT"


@dataclass(frozen=True)
class ProtectedActionIntent:
    capability: str
    protected_arguments: bytes
    session_id: str
    operation_id: str
    action_kind: ActionKind


@dataclass(frozen=True)
class AgentServiceRouteDescriptor:
    route_handle: str
    effect_semantics: EffectSemantics
    policy_id: str
    placement: PlacementClass

    def validated(self) -> "AgentServiceRouteDescriptor":
        if not self.route_handle or not self.policy_id:
            raise ValueError("Agent-service route is incomplete")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ValueError("invalid Agent-service effect semantics")
        if not isinstance(self.placement, PlacementClass):
            raise ValueError("invalid Agent-service placement")
        return self


@dataclass(frozen=True)
class AgentDescriptorV7:
    agent_id: int
    capability_ids: tuple[str, ...]
    publisher_key_id: str
    agent_version: int
    placement: PlacementClass
    agent_service: AgentServiceRouteDescriptor | None
    allowed_tool_capabilities: tuple[str, ...]
    trust_class: str
    catalog_epoch: int

    def validated(self) -> "AgentDescriptorV7":
        if self.agent_id < 0 or self.agent_version < 0 or self.catalog_epoch < 0:
            raise ValueError("negative descriptor identifier/version/epoch")
        if not self.capability_ids or not self.publisher_key_id or not self.trust_class:
            raise ValueError("descriptor omits required metadata")
        if not isinstance(self.placement, PlacementClass):
            raise ValueError("invalid Agent placement")
        if self.agent_service is not None:
            self.agent_service.validated()
            if self.agent_service.placement is not self.placement:
                raise ValueError("Agent and Agent-service placement disagree")
        return self


@dataclass(frozen=True)
class ActionRouteDescriptor:
    capability: str
    route_handle: str
    action_kind: ActionKind
    placement: PlacementClass
    effect_semantics: EffectSemantics
    policy_id: str

    def validated(self) -> "ActionRouteDescriptor":
        if not self.capability or not self.route_handle or not self.policy_id:
            raise ValueError("action route descriptor is incomplete")
        if self.action_kind not in (ActionKind.TOOL, ActionKind.EXTERNAL_HTTP):
            raise ValueError("action route map accepts only TOOL/EXTERNAL_HTTP")
        if not isinstance(self.placement, PlacementClass):
            raise ValueError("invalid action placement")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ValueError("invalid action effect semantics")
        return self


@dataclass(frozen=True)
class DeploymentPolicy:
    strict_common_broker_routes: frozenset[str] = frozenset()
    confidential_cloud_routes: frozenset[str] = frozenset()
    efficient_allow_cloud_local: bool = True


@dataclass(frozen=True)
class ResolvedAction:
    action_kind: ActionKind
    route_handle: str | None
    operation_id: str
    protected_arguments: bytes
    effect_semantics: EffectSemantics
    policy_id: str
    placement: PlacementClass | None
    public_route_class: str
    declared_public_leakage: str

