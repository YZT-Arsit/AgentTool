from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import asdict, dataclass
from enum import StrEnum

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DESCRIPTOR_BYTES = 1024
NONCE_BYTES = 12
TAG_BYTES = 16
PLAINTEXT_BYTES = DESCRIPTOR_BYTES - NONCE_BYTES - TAG_BYTES
MAGIC = "ATD6"
SCHEMA_VERSION = 6


class PlacementClass(StrEnum):
    TRUSTED_MODULE_LOCAL = "TRUSTED_MODULE_LOCAL"
    CLOUD_LOCAL = "CLOUD_LOCAL"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class AgentDescriptorV6:
    agent_id: int
    capability_ids: tuple[str, ...]
    publisher_key_id: str
    agent_version: int
    placement: PlacementClass
    gateway_route_handle: str
    runtime_metadata: str
    allowed_tool_capabilities: tuple[str, ...]
    trust_class: str
    catalog_epoch: int

    def validated(self) -> "AgentDescriptorV6":
        if self.agent_id < 0 or self.agent_version < 0 or self.catalog_epoch < 0:
            raise ValueError("negative descriptor identifier/version/epoch")
        if not self.capability_ids or not self.publisher_key_id or not self.gateway_route_handle:
            raise ValueError("descriptor omits required routing metadata")
        return self

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value["placement"] = self.placement.value
        value["capability_ids"] = list(self.capability_ids)
        value["allowed_tool_capabilities"] = list(self.allowed_tool_capabilities)
        return value


class DescriptorCodec:
    """Fixed-width authenticated descriptor encryption.

    SimplePIR treats the returned 1024 bytes as opaque.  AEAD provides record
    confidentiality/integrity; PIR provides index privacy against its server.
    """

    def __init__(self, key: bytes, catalog_epoch: int):
        if len(key) not in (16, 24, 32):
            raise ValueError("invalid descriptor AEAD key")
        self._aead = AESGCM(key)
        self.catalog_epoch = catalog_epoch

    def _aad(self) -> bytes:
        return b"AgentTool|AgentDescriptorV6|" + self.catalog_epoch.to_bytes(8, "big")

    def encode(self, descriptor: AgentDescriptorV6) -> bytes:
        descriptor.validated()
        if descriptor.catalog_epoch != self.catalog_epoch:
            raise ValueError("descriptor catalog epoch mismatch")
        body = descriptor.canonical_payload()
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        envelope = {"magic": MAGIC, "schema_version": SCHEMA_VERSION,
                    "descriptor": body, "descriptor_digest": digest}
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) + 4 > PLAINTEXT_BYTES:
            raise ValueError("descriptor exceeds fixed-width record")
        plain = struct.pack("!I", len(raw)) + raw + os.urandom(PLAINTEXT_BYTES - 4 - len(raw))
        nonce = os.urandom(NONCE_BYTES)
        encoded = nonce + self._aead.encrypt(nonce, plain, self._aad())
        if len(encoded) != DESCRIPTOR_BYTES:
            raise AssertionError("descriptor row width changed")
        return encoded

    def decode(self, row: bytes, expected_agent_id: int) -> AgentDescriptorV6:
        if len(row) != DESCRIPTOR_BYTES:
            raise ValueError("invalid descriptor row width")
        plain = self._aead.decrypt(row[:NONCE_BYTES], row[NONCE_BYTES:], self._aad())
        length = struct.unpack("!I", plain[:4])[0]
        if length > PLAINTEXT_BYTES - 4:
            raise ValueError("invalid descriptor payload length")
        envelope = json.loads(plain[4:4 + length])
        if envelope.get("magic") != MAGIC or envelope.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("invalid descriptor schema")
        body = envelope["descriptor"]
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != envelope.get("descriptor_digest"):
            raise ValueError("descriptor digest mismatch")
        descriptor = AgentDescriptorV6(
            agent_id=int(body["agent_id"]), capability_ids=tuple(body["capability_ids"]),
            publisher_key_id=str(body["publisher_key_id"]), agent_version=int(body["agent_version"]),
            placement=PlacementClass(body["placement"]), gateway_route_handle=str(body["gateway_route_handle"]),
            runtime_metadata=str(body["runtime_metadata"]),
            allowed_tool_capabilities=tuple(body["allowed_tool_capabilities"]),
            trust_class=str(body["trust_class"]), catalog_epoch=int(body["catalog_epoch"]),
        ).validated()
        if descriptor.agent_id != expected_agent_id:
            raise PermissionError("descriptor Agent ID does not match private selection")
        if descriptor.catalog_epoch != self.catalog_epoch:
            raise PermissionError("descriptor catalog epoch is stale")
        return descriptor
