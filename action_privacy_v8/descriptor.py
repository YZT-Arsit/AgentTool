from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import asdict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import (
    AgentDescriptorV7,
    AgentServiceRouteDescriptor,
    EffectSemantics,
    PlacementClass,
)


AGENT_DESCRIPTOR_V7_BYTES = 1024
NONCE_BYTES = 12
TAG_BYTES = 16
PLAIN_BYTES = AGENT_DESCRIPTOR_V7_BYTES - NONCE_BYTES - TAG_BYTES
MAGIC = "ATD7"
SCHEMA_VERSION = 7


class AgentDescriptorV7Codec:
    """Fixed-width authenticated AgentDescriptorV7 rows for SimplePIR."""

    def __init__(self, key: bytes, catalog_epoch: int):
        if len(key) not in (16, 24, 32):
            raise ValueError("invalid descriptor AEAD key")
        if catalog_epoch < 0:
            raise ValueError("negative catalog epoch")
        self._aead = AESGCM(key)
        self.catalog_epoch = catalog_epoch

    def _aad(self) -> bytes:
        return b"AgentTool|AgentDescriptorV7|" + self.catalog_epoch.to_bytes(8, "big")

    @staticmethod
    def _body(descriptor: AgentDescriptorV7) -> dict[str, object]:
        descriptor.validated()
        service = None
        if descriptor.agent_service is not None:
            service = asdict(descriptor.agent_service)
            service["effect_semantics"] = descriptor.agent_service.effect_semantics.value
            service["placement"] = descriptor.agent_service.placement.value
        return {
            "agent_id": descriptor.agent_id,
            "capability_ids": list(descriptor.capability_ids),
            "publisher_key_id": descriptor.publisher_key_id,
            "agent_version": descriptor.agent_version,
            "placement": descriptor.placement.value,
            "agent_service": service,
            "allowed_tool_capabilities": list(descriptor.allowed_tool_capabilities),
            "trust_class": descriptor.trust_class,
            "catalog_epoch": descriptor.catalog_epoch,
        }

    def encode(self, descriptor: AgentDescriptorV7) -> bytes:
        if descriptor.catalog_epoch != self.catalog_epoch:
            raise ValueError("descriptor catalog epoch mismatch")
        body = self._body(descriptor)
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        envelope = {
            "magic": MAGIC,
            "schema_version": SCHEMA_VERSION,
            "descriptor": body,
            "descriptor_digest": hashlib.sha256(canonical).hexdigest(),
            "version_binding": f"{descriptor.agent_version}:{descriptor.catalog_epoch}",
        }
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) + 4 > PLAIN_BYTES:
            raise ValueError("AgentDescriptorV7 exceeds fixed PIR row")
        plain = struct.pack("!I", len(raw)) + raw + os.urandom(PLAIN_BYTES - 4 - len(raw))
        nonce = os.urandom(NONCE_BYTES)
        encoded = nonce + self._aead.encrypt(nonce, plain, self._aad())
        if len(encoded) != AGENT_DESCRIPTOR_V7_BYTES:
            raise AssertionError("AgentDescriptorV7 row width changed")
        return encoded

    def decode(self, row: bytes, expected_agent_id: int) -> AgentDescriptorV7:
        if len(row) != AGENT_DESCRIPTOR_V7_BYTES:
            raise ValueError("invalid AgentDescriptorV7 row width")
        plain = self._aead.decrypt(row[:NONCE_BYTES], row[NONCE_BYTES:], self._aad())
        length = struct.unpack("!I", plain[:4])[0]
        if length > PLAIN_BYTES - 4:
            raise ValueError("invalid AgentDescriptorV7 payload length")
        envelope = json.loads(plain[4:4 + length])
        if envelope.get("magic") != MAGIC or envelope.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("invalid AgentDescriptorV7 schema")
        body = envelope.get("descriptor")
        if not isinstance(body, dict):
            raise ValueError("missing AgentDescriptorV7 body")
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if digest != envelope.get("descriptor_digest"):
            raise ValueError("AgentDescriptorV7 digest mismatch")
        if envelope.get("version_binding") != f"{body.get('agent_version')}:{body.get('catalog_epoch')}":
            raise ValueError("AgentDescriptorV7 version binding mismatch")
        service_body = body.get("agent_service")
        service = None
        if service_body is not None:
            if not isinstance(service_body, dict):
                raise ValueError("malformed Agent-service descriptor")
            service = AgentServiceRouteDescriptor(
                route_handle=str(service_body["route_handle"]),
                effect_semantics=EffectSemantics(service_body["effect_semantics"]),
                policy_id=str(service_body["policy_id"]),
                placement=PlacementClass(service_body["placement"]),
            )
        descriptor = AgentDescriptorV7(
            agent_id=int(body["agent_id"]),
            capability_ids=tuple(str(item) for item in body["capability_ids"]),
            publisher_key_id=str(body["publisher_key_id"]),
            agent_version=int(body["agent_version"]),
            placement=PlacementClass(body["placement"]),
            agent_service=service,
            allowed_tool_capabilities=tuple(str(item) for item in body["allowed_tool_capabilities"]),
            trust_class=str(body["trust_class"]),
            catalog_epoch=int(body["catalog_epoch"]),
        ).validated()
        if descriptor.agent_id != expected_agent_id:
            raise PermissionError("descriptor Agent ID does not match private selection")
        if descriptor.catalog_epoch != self.catalog_epoch:
            raise PermissionError("descriptor catalog epoch is stale")
        return descriptor

