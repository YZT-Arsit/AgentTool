from __future__ import annotations

from .models import (
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    DeploymentPolicy,
    EffectSemantics,
    PlacementClass,
    PrivacyProfile,
    ProtectedActionIntent,
    ResolvedAction,
)


class TrustedActionRouter:
    def __init__(
        self,
        action_routes: dict[str, ActionRouteDescriptor],
        deployment: DeploymentPolicy | None = None,
    ):
        self._routes = {key: value.validated() for key, value in action_routes.items()}
        self._deployment = deployment or DeploymentPolicy()
        for key, value in self._routes.items():
            if key != value.capability:
                raise ValueError("action route map key/capability mismatch")

    def _placement(self, placement: PlacementClass, route: str, profile: PrivacyProfile) -> tuple[str, str]:
        if placement is PlacementClass.TRUSTED_MODULE_LOCAL:
            return "TRUSTED_MODULE_LOCAL", "NONE"
        if placement is PlacementClass.EXTERNAL:
            return "OHTTP_ACTION_GATEWAY", "NONE" if profile is PrivacyProfile.STRICT else "EXTERNAL_ROUTE_CLASS"
        if profile is PrivacyProfile.STRICT:
            if route not in self._deployment.strict_common_broker_routes:
                raise PermissionError("STRICT rejects distinct CLOUD_LOCAL route")
            return "COMMON_CONFIDENTIAL_BROKER", "NONE"
        if profile is PrivacyProfile.CONFIDENTIAL_ENTERPRISE:
            if route not in self._deployment.confidential_cloud_routes:
                raise PermissionError("CLOUD_LOCAL route is outside declared confidential deployment")
            return "CONFIDENTIAL_CLOUD_ROUTE", "INTERNAL_EXTERNAL_ROUTE_CLASS"
        if not self._deployment.efficient_allow_cloud_local:
            raise PermissionError("enterprise-efficient CLOUD_LOCAL routing disabled")
        return "CLOUD_LOCAL_DIRECT", "CLOUD_LOCAL_ACTION_CLASS"

    def resolve(
        self,
        intent: ProtectedActionIntent,
        agent: AgentDescriptorV7,
        profile: PrivacyProfile,
    ) -> ResolvedAction:
        agent.validated()
        if not isinstance(profile, PrivacyProfile):
            raise ValueError("unknown privacy profile")
        if intent.action_kind is ActionKind.NOOP:
            return ResolvedAction(ActionKind.NOOP, None, intent.operation_id, b"",
                                  EffectSemantics.READ_ONLY, "NOOP", None,
                                  "NO_REAL_ROUTE", "NONE")
        if intent.action_kind is ActionKind.AGENT_SERVICE:
            if intent.capability not in agent.capability_ids:
                raise PermissionError("Agent-service capability is not authorized")
            if agent.agent_service is None:
                raise LookupError("Agent-service route is absent")
            route_class, leakage = self._placement(
                agent.agent_service.placement, agent.agent_service.route_handle, profile
            )
            return ResolvedAction(
                ActionKind.AGENT_SERVICE, agent.agent_service.route_handle,
                intent.operation_id, intent.protected_arguments,
                agent.agent_service.effect_semantics, agent.agent_service.policy_id,
                agent.agent_service.placement, route_class, leakage,
            )
        if intent.capability not in agent.allowed_tool_capabilities:
            raise PermissionError("Tool/action capability is not authorized by Agent")
        route = self._routes.get(intent.capability)
        if route is None:
            raise LookupError("authorized capability has no trusted route")
        if route.action_kind is not intent.action_kind:
            raise PermissionError("action kind does not match trusted route")
        route_class, leakage = self._placement(route.placement, route.route_handle, profile)
        return ResolvedAction(
            intent.action_kind, route.route_handle, intent.operation_id,
            intent.protected_arguments, route.effect_semantics, route.policy_id,
            route.placement, route_class, leakage,
        )

