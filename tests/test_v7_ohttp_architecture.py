from __future__ import annotations

import pytest

from action_privacy_v7_ohttp import (
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    CanonicalTransportUnavailable,
    EffectSemantics,
    LegacyDevTransportMarker,
    PlacementClass,
    ProtectedActionIntent,
    RFC9458BackendUnavailable,
    TrustedActionRouter,
)


def agent() -> AgentDescriptorV7:
    return AgentDescriptorV7(
        agent_id=7,
        capability_ids=("agent.weather",),
        publisher_key_id="publisher-test",
        agent_version=1,
        placement=PlacementClass.EXTERNAL,
        agent_service_route_handle="agent-route-7",
        allowed_tool_capabilities=("tool.weather", "external.records"),
        trust_class="SIGNED_ENTERPRISE",
        catalog_epoch=4,
    )


def router() -> TrustedActionRouter:
    return TrustedActionRouter(
        {
            "tool.weather": ActionRouteDescriptor(
                "tool.weather", "tool-route-weather", ActionKind.TOOL,
                PlacementClass.EXTERNAL, EffectSemantics.READ_ONLY, "policy-weather"
            ),
            "external.records": ActionRouteDescriptor(
                "external.records", "external-route-records", ActionKind.EXTERNAL_HTTP,
                PlacementClass.EXTERNAL, EffectSemantics.IDEMPOTENT_EFFECT, "policy-records"
            ),
        }
    )


def intent(capability: str, kind: ActionKind) -> ProtectedActionIntent:
    return ProtectedActionIntent(capability, b"synthetic", "session", "op-1", kind)


def test_agent_service_route_is_used_only_for_agent_service():
    routed = router().resolve(intent("agent.weather", ActionKind.AGENT_SERVICE), agent())
    assert routed.route_handle == "agent-route-7"
    tool = router().resolve(intent("tool.weather", ActionKind.TOOL), agent())
    assert tool.route_handle == "tool-route-weather"
    assert tool.route_handle != routed.route_handle


def test_tool_and_external_routes_require_agent_authorization_and_kind_match():
    external = router().resolve(intent("external.records", ActionKind.EXTERNAL_HTTP), agent())
    assert external.route_handle == "external-route-records"
    assert external.effect_semantics is EffectSemantics.IDEMPOTENT_EFFECT
    with pytest.raises(PermissionError):
        router().resolve(intent("tool.unapproved", ActionKind.TOOL), agent())
    with pytest.raises(PermissionError):
        router().resolve(intent("tool.weather", ActionKind.EXTERNAL_HTTP), agent())


def test_noop_has_no_real_route_and_no_arguments():
    routed = router().resolve(intent("ignored", ActionKind.NOOP), agent())
    assert routed.route_handle is None
    assert routed.protected_arguments == b""


def test_legacy_wire_cannot_be_promoted_to_canonical_ohttp():
    marker = LegacyDevTransportMarker()
    assert not marker.rfc9458_wire and not marker.canonical
    with pytest.raises(CanonicalTransportUnavailable):
        marker.require_canonical()


def test_missing_offline_rfc9458_backend_fails_closed():
    backend = RFC9458BackendUnavailable()
    assert not backend.rfc9458_wire
    with pytest.raises(CanonicalTransportUnavailable):
        backend.encapsulate_request(b"not-bhttp")
