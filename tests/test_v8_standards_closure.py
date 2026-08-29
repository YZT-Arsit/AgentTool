from __future__ import annotations

import hashlib
import json
import struct

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from action_privacy_v8 import (
    AGENT_DESCRIPTOR_V7_BYTES,
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    AgentDescriptorV7Codec,
    AgentServiceRouteDescriptor,
    DeliveryLedger,
    DeliveryState,
    DeploymentPolicy,
    EffectSemantics,
    FrameworkDeliveryDecision,
    PlacementClass,
    PrivacyProfile,
    ProtectedActionIntent,
    TrustedActionRouter,
)
from action_privacy_v8.descriptor import MAGIC, NONCE_BYTES, PLAIN_BYTES, SCHEMA_VERSION
from action_privacy_v8.pir_boundary import audit_server_log


KEY = bytes(range(32))
EPOCH = 20260828


def service(
    semantics: EffectSemantics = EffectSemantics.READ_ONLY,
    placement: PlacementClass = PlacementClass.EXTERNAL,
    route: str = "agent-service-route",
) -> AgentServiceRouteDescriptor:
    return AgentServiceRouteDescriptor(route, semantics, "agent-service-policy", placement)


def descriptor(
    semantics: EffectSemantics = EffectSemantics.READ_ONLY,
    placement: PlacementClass = PlacementClass.EXTERNAL,
    route: str = "agent-service-route",
) -> AgentDescriptorV7:
    return AgentDescriptorV7(
        7, ("agent.weather",), "publisher-test", 3, placement,
        service(semantics, placement, route), ("tool.weather", "external.records"),
        "SIGNED_ENTERPRISE", EPOCH,
    )


def routes(placement: PlacementClass = PlacementClass.EXTERNAL) -> dict[str, ActionRouteDescriptor]:
    return {
        "tool.weather": ActionRouteDescriptor(
            "tool.weather", "tool-route", ActionKind.TOOL, placement,
            EffectSemantics.READ_ONLY, "tool-policy",
        ),
        "external.records": ActionRouteDescriptor(
            "external.records", "external-route", ActionKind.EXTERNAL_HTTP,
            PlacementClass.EXTERNAL, EffectSemantics.IDEMPOTENT_EFFECT, "external-policy",
        ),
    }


def intent(capability: str, kind: ActionKind) -> ProtectedActionIntent:
    return ProtectedActionIntent(capability, b"synthetic", "session", "operation-1", kind)


def test_descriptor_v7_fixed_authenticated_and_bound_to_agent_epoch():
    codec = AgentDescriptorV7Codec(KEY, EPOCH)
    row = codec.encode(descriptor(EffectSemantics.NON_IDEMPOTENT_EFFECT))
    assert len(row) == AGENT_DESCRIPTOR_V7_BYTES
    recovered = codec.decode(row, 7)
    assert recovered == descriptor(EffectSemantics.NON_IDEMPOTENT_EFFECT)
    corrupt = bytearray(row)
    corrupt[-1] ^= 1
    with pytest.raises(Exception):
        codec.decode(bytes(corrupt), 7)
    with pytest.raises(PermissionError):
        codec.decode(row, 8)
    with pytest.raises(Exception):
        AgentDescriptorV7Codec(KEY, EPOCH + 1).decode(row, 7)


def _authenticated_row_with_body(body: dict[str, object], *, magic: str = MAGIC, schema: int = SCHEMA_VERSION) -> bytes:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    envelope = {
        "magic": magic,
        "schema_version": schema,
        "descriptor": body,
        "descriptor_digest": hashlib.sha256(canonical).hexdigest(),
        "version_binding": f"{body['agent_version']}:{body['catalog_epoch']}",
    }
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    plain = struct.pack("!I", len(raw)) + raw + bytes(PLAIN_BYTES - 4 - len(raw))
    nonce = bytes(NONCE_BYTES)
    aad = b"AgentTool|AgentDescriptorV7|" + EPOCH.to_bytes(8, "big")
    return nonce + AESGCM(KEY).encrypt(nonce, plain, aad)


def test_descriptor_v7_rejects_authenticated_malformed_enum_and_schema():
    codec = AgentDescriptorV7Codec(KEY, EPOCH)
    body = codec._body(descriptor())
    body["placement"] = "NOT_A_PLACEMENT"
    with pytest.raises(ValueError):
        codec.decode(_authenticated_row_with_body(body), 7)
    body = codec._body(descriptor())
    with pytest.raises(ValueError):
        codec.decode(_authenticated_row_with_body(body, schema=99), 7)


@pytest.mark.parametrize(
    "semantics",
    [EffectSemantics.READ_ONLY, EffectSemantics.IDEMPOTENT_EFFECT,
     EffectSemantics.NON_IDEMPOTENT_EFFECT],
)
def test_agent_service_preserves_declared_effect_semantics(semantics: EffectSemantics):
    resolved = TrustedActionRouter(routes()).resolve(
        intent("agent.weather", ActionKind.AGENT_SERVICE), descriptor(semantics), PrivacyProfile.STRICT
    )
    assert resolved.effect_semantics is semantics
    assert resolved.route_handle == "agent-service-route"


def test_strict_rejects_visible_cloud_local_and_never_downgrades():
    cloud_agent = descriptor(placement=PlacementClass.CLOUD_LOCAL, route="cloud-agent-route")
    router = TrustedActionRouter(routes(PlacementClass.CLOUD_LOCAL))
    with pytest.raises(PermissionError):
        router.resolve(intent("agent.weather", ActionKind.AGENT_SERVICE), cloud_agent, PrivacyProfile.STRICT)
    with pytest.raises(PermissionError):
        router.resolve(intent("tool.weather", ActionKind.TOOL), cloud_agent, PrivacyProfile.STRICT)
    with pytest.raises(ValueError):
        router.resolve(intent("tool.weather", ActionKind.TOOL), cloud_agent, "STRICT")  # type: ignore[arg-type]


def test_profiles_require_explicit_cloud_local_policy_and_record_leakage():
    cloud_agent = descriptor(placement=PlacementClass.CLOUD_LOCAL, route="cloud-agent-route")
    policy = DeploymentPolicy(
        strict_common_broker_routes=frozenset({"tool-route"}),
        confidential_cloud_routes=frozenset({"cloud-agent-route", "tool-route"}),
    )
    router = TrustedActionRouter(routes(PlacementClass.CLOUD_LOCAL), policy)
    strict_tool = router.resolve(intent("tool.weather", ActionKind.TOOL), cloud_agent, PrivacyProfile.STRICT)
    assert strict_tool.public_route_class == "COMMON_CONFIDENTIAL_BROKER"
    confidential = router.resolve(
        intent("agent.weather", ActionKind.AGENT_SERVICE), cloud_agent,
        PrivacyProfile.CONFIDENTIAL_ENTERPRISE,
    )
    assert confidential.declared_public_leakage == "INTERNAL_EXTERNAL_ROUTE_CLASS"
    efficient = router.resolve(
        intent("tool.weather", ActionKind.TOOL), cloud_agent, PrivacyProfile.ENTERPRISE_EFFICIENT
    )
    assert efficient.declared_public_leakage == "CLOUD_LOCAL_ACTION_CLASS"


def test_tool_route_is_separate_from_agent_service_route_and_unauthorized_fails():
    router = TrustedActionRouter(routes())
    agent_result = router.resolve(
        intent("agent.weather", ActionKind.AGENT_SERVICE), descriptor(), PrivacyProfile.STRICT
    )
    tool_result = router.resolve(intent("tool.weather", ActionKind.TOOL), descriptor(), PrivacyProfile.STRICT)
    assert agent_result.route_handle != tool_result.route_handle
    with pytest.raises(PermissionError):
        router.resolve(intent("tool.forbidden", ActionKind.TOOL), descriptor(), PrivacyProfile.STRICT)


def test_trusted_delivery_ledger_suppresses_durable_duplicate(tmp_path):
    path = tmp_path / "delivery.json"
    ledger = DeliveryLedger(path)
    ledger.record_received("op")
    ledger.mark_decapsulated("op")
    delivered: list[str] = []
    assert ledger.deliver("op", lambda: delivered.append("op")) is FrameworkDeliveryDecision.DELIVER
    restarted = DeliveryLedger(path)
    assert restarted.deliver("op", lambda: delivered.append("duplicate")) is FrameworkDeliveryDecision.SUPPRESS_ALREADY_DELIVERED
    assert delivered == ["op"]


def test_trusted_delivery_ledger_crash_before_framework_delivery_remains_deliverable(tmp_path):
    path = tmp_path / "delivery.json"
    ledger = DeliveryLedger(path)
    ledger.record_received("op")
    ledger.mark_decapsulated("op")
    restarted = DeliveryLedger(path)
    assert restarted.state("op") is DeliveryState.DECAPSULATED
    assert restarted.decision("op") is FrameworkDeliveryDecision.DELIVER


def test_pir_server_log_audit_separates_private_client_fields():
    audit_server_log('{"ordinal":1,"query_bytes":2020,"executor":"SimplePIRServer"}')
    with pytest.raises(AssertionError):
        audit_server_log('{"agent_id":7}')

