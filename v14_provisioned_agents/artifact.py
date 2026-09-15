from __future__ import annotations

import hashlib
import json
import os
import struct

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .models import ProvisionedAgentArtifactV1, canonical_json


PIR_RECORD_BYTES = 1024
NONCE_BYTES = 12
TAG_BYTES = 16
PLAIN_BYTES = PIR_RECORD_BYTES - NONCE_BYTES - TAG_BYTES
HEADER = struct.Struct(">4sHHI")
MAGIC = b"OAPA"
AAD_PREFIX = b"OAE|ProvisionedAgentArtifactV1|"


class ArtifactValidationError(RuntimeError):
    pass


class ProvisionedAgentArtifactCodec:
    """Canonical JSON -> AES-GCM -> random padding -> fixed SimplePIR row."""

    def __init__(self, key: bytes, store_epoch: int):
        if len(key) not in (16, 24, 32):
            raise ValueError("artifact AEAD key must be 128, 192, or 256 bits")
        if not 0 <= store_epoch < 2**64:
            raise ValueError("invalid store epoch")
        self._aead = AESGCM(key)
        self.store_epoch = store_epoch

    def _aad(self) -> bytes:
        return AAD_PREFIX + self.store_epoch.to_bytes(8, "big")

    @staticmethod
    def serialized_plaintext(artifact: ProvisionedAgentArtifactV1) -> bytes:
        body = artifact.canonical_body()
        return canonical_json(
            {
                "artifact": body,
                "artifact_digest": hashlib.sha256(canonical_json(body)).hexdigest(),
                "magic": "OAPA",
                "schema": "ProvisionedAgentArtifactV1",
            }
        )

    @classmethod
    def plaintext_size(cls, artifact: ProvisionedAgentArtifactV1) -> int:
        return len(cls.serialized_plaintext(artifact))

    @property
    def payload_capacity(self) -> int:
        return PLAIN_BYTES - HEADER.size

    def encode(self, artifact: ProvisionedAgentArtifactV1) -> bytes:
        artifact = artifact.validated()
        if artifact.store_epoch != self.store_epoch:
            raise ValueError("artifact store epoch mismatch")
        payload = self.serialized_plaintext(artifact)
        if len(payload) > self.payload_capacity:
            raise ValueError(
                f"artifact needs {len(payload)} bytes but fixed row permits "
                f"{self.payload_capacity}"
            )
        plain = (
            HEADER.pack(MAGIC, 1, 0, len(payload))
            + payload
            + os.urandom(self.payload_capacity - len(payload))
        )
        nonce = os.urandom(NONCE_BYTES)
        result = nonce + self._aead.encrypt(nonce, plain, self._aad())
        if len(result) != PIR_RECORD_BYTES:
            raise AssertionError("PIR record width changed")
        return result

    def decode(self, row: bytes, expected_agent_id: int) -> ProvisionedAgentArtifactV1:
        if len(row) != PIR_RECORD_BYTES:
            raise ArtifactValidationError("PIR row width is invalid")
        try:
            plain = self._aead.decrypt(row[:NONCE_BYTES], row[NONCE_BYTES:], self._aad())
        except Exception as exc:
            raise ArtifactValidationError("artifact authentication failed") from exc
        magic, version, flags, length = HEADER.unpack_from(plain)
        if magic != MAGIC or version != 1 or flags != 0 or length > self.payload_capacity:
            raise ArtifactValidationError("artifact envelope is invalid")
        try:
            envelope = json.loads(plain[HEADER.size : HEADER.size + length])
        except Exception as exc:
            raise ArtifactValidationError("artifact JSON is malformed") from exc
        if envelope.get("magic") != "OAPA" or envelope.get("schema") != "ProvisionedAgentArtifactV1":
            raise ArtifactValidationError("artifact schema binding failed")
        body = envelope.get("artifact")
        if hashlib.sha256(canonical_json(body)).hexdigest() != envelope.get("artifact_digest"):
            raise ArtifactValidationError("artifact digest mismatch")
        artifact = ProvisionedAgentArtifactV1.from_body(body)
        if artifact.canonical_agent_id != expected_agent_id:
            raise ArtifactValidationError("artifact AgentID binding failed")
        if artifact.store_epoch != self.store_epoch:
            raise ArtifactValidationError("artifact store epoch is stale")
        return artifact
