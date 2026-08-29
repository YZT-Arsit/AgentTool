from __future__ import annotations

from .models import (
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    EffectSemantics,
    ProtectedActionIntent,
    ResolvedAction,
)


class TrustedActionRouter:
    """Authorization-preserving private route resolution.

    The route map is trusted-memory state in this prototype.  No second PIR is
    implied.  The returned route is intended for the trusted OHTTP Gateway
    plaintext, never the relay view.
    """

    def __init__(self, action_routes: dict[str, ActionRouteDescriptor]):
        self._routes = {
            capability: descriptor.validated()
            for capability, descriptor in action_routes.items()
        }
        for capability, descriptor in self._routes.items():
            if capability != descriptor.capability:
                raise ValueError("action route map key/capability mismatch")

    def resolve(
        self, intent: ProtectedActionIntent, agent: AgentDescriptorV7
    ) -> ResolvedAction:
        agent.validated()
        if intent.action_kind is ActionKind.NOOP:
            return ResolvedAction(
                ActionKind.NOOP,
                None,
                intent.operation_id,
                b"",
                EffectSemantics.READ_ONLY,
                "NOOP",
            )

        if intent.action_kind is ActionKind.AGENT_SERVICE:
            if intent.capability not in agent.capability_ids:
                raise PermissionError("Agent service capability is not authorized")
            if not agent.agent_service_route_handle:
                raise LookupError("Agent service route is absent")
            return ResolvedAction(
                ActionKind.AGENT_SERVICE,
                agent.agent_service_route_handle,
                intent.operation_id,
                intent.protected_arguments,
                EffectSemantics.READ_ONLY,
                "AGENT_SERVICE_POLICY",
            )

        if intent.capability not in agent.allowed_tool_capabilities:
            raise PermissionError("Tool/action capability is not authorized by Agent")
        route = self._routes.get(intent.capability)
        if route is None:
            raise LookupError("authorized action capability has no trusted route")
        if route.action_kind is not intent.action_kind:
            raise PermissionError("action kind does not match trusted route descriptor")
        return ResolvedAction(
            intent.action_kind,
            route.route_handle,
            intent.operation_id,
            intent.protected_arguments,
            route.effect_semantics,
            route.policy_id,
        )

