from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


class AttestationStatus(StrEnum):
    HARDWARE_TEE_ATTESTATION_NOT_TESTED = "HARDWARE_TEE_ATTESTATION_NOT_TESTED"
    LOCAL_FUNCTIONAL_EVIDENCE_ONLY = "LOCAL_FUNCTIONAL_EVIDENCE_ONLY"


@dataclass(frozen=True)
class AttestationEvidence:
    backend: str
    measurement: str
    ephemeral_public_key_b64: str
    issued_monotonic_ns: int
    nonce_b64: str
    status: AttestationStatus
    hardware_signed: bool

    def public_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "measurement": self.measurement,
            "ephemeral_public_key_b64": self.ephemeral_public_key_b64,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "nonce_b64": self.nonce_b64,
            "status": self.status.value,
            "hardware_signed": self.hardware_signed,
        }


@dataclass(frozen=True)
class ProvisionedSession:
    session_id: str
    payload_key: bytes
    transcript_key: bytes
    evidence: AttestationEvidence


@dataclass(frozen=True)
class EnterpriseAttestationPolicy:
    approved_measurements: frozenset[str]
    allow_local_functional_backend: bool = False

    def verify(self, evidence: AttestationEvidence, expected_nonce: bytes) -> None:
        if evidence.measurement not in self.approved_measurements:
            raise PermissionError("unapproved confidential-runtime measurement")
        if base64.b64decode(evidence.nonce_b64) != expected_nonce:
            raise PermissionError("attestation challenge mismatch")
        if not evidence.hardware_signed and not self.allow_local_functional_backend:
            raise PermissionError("hardware-signed attestation required")


def measure_files(root: Path, relative_paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(relative_paths)):
        path = (root / relative).resolve()
        if root.resolve() not in path.parents:
            raise ValueError("measurement path leaves repository root")
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class LocalTrustedProcessBackend:
    """Functional TEE API with no hostile-host isolation claim.

    It exercises measurement allow-listing, challenge binding, ephemeral X25519
    session establishment, AEAD payload handling, restart/key-rotation behavior,
    and a sealed-state format.  The host can inspect memory and can roll back the
    sealed file, so hardware attestation and rollback resistance remain untested.
    """

    backend_name = "LOCAL_TRUSTED_PROCESS_FUNCTIONAL_ONLY"
    hardware_attestation = AttestationStatus.HARDWARE_TEE_ATTESTATION_NOT_TESTED
    rollback_protection = "NOT_IMPLEMENTED_WITHOUT_TRUSTED_MONOTONIC_ANCHOR"

    def __init__(self, measurement: str, *, sealing_key: bytes | None = None):
        self.measurement = measurement
        self._ephemeral_private: X25519PrivateKey | None = None
        self._sealing_key = sealing_key or os.urandom(32)
        self._boot_id = os.urandom(16).hex()

    def attest(self, challenge: bytes) -> AttestationEvidence:
        if len(challenge) < 16:
            raise ValueError("attestation challenge must contain at least 128 bits")
        self._ephemeral_private = X25519PrivateKey.generate()
        public = self._ephemeral_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return AttestationEvidence(
            self.backend_name, self.measurement, base64.b64encode(public).decode("ascii"),
            time.monotonic_ns(), base64.b64encode(challenge).decode("ascii"),
            AttestationStatus.LOCAL_FUNCTIONAL_EVIDENCE_ONLY, False,
        )

    def provision(self, evidence: AttestationEvidence, enterprise_private: X25519PrivateKey,
                  policy: EnterpriseAttestationPolicy, challenge: bytes) -> ProvisionedSession:
        policy.verify(evidence, challenge)
        if self._ephemeral_private is None:
            raise RuntimeError("runtime has not produced attestation evidence")
        peer_public = X25519PublicKey.from_public_bytes(base64.b64decode(evidence.ephemeral_public_key_b64))
        # Both expressions derive the same shared secret; compute both in the
        # functional backend so tests catch transcript/key-flow mistakes.
        runtime_shared = self._ephemeral_private.exchange(enterprise_private.public_key())
        enterprise_shared = enterprise_private.exchange(peer_public)
        if runtime_shared != enterprise_shared:
            raise AssertionError("session key agreement mismatch")
        transcript = json.dumps(evidence.public_dict(), sort_keys=True, separators=(",", ":")).encode()
        material = HKDF(algorithm=hashes.SHA256(), length=64, salt=challenge,
                        info=b"AgentTool-V5-TEE-bootstrap|" + hashlib.sha256(transcript).digest()).derive(runtime_shared)
        return ProvisionedSession(self._boot_id, material[:32], material[32:], evidence)

    @staticmethod
    def encrypt_payload(session: ProvisionedSession, plaintext: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + AESGCM(session.payload_key).encrypt(nonce, plaintext, aad)

    @staticmethod
    def decrypt_payload(session: ProvisionedSession, ciphertext: bytes, aad: bytes) -> bytes:
        if len(ciphertext) < 28:
            raise ValueError("short protected payload")
        return AESGCM(session.payload_key).decrypt(ciphertext[:12], ciphertext[12:], aad)

    def seal(self, state: bytes, *, epoch: int, domain: bytes = b"AgentTool-V5-sealed-state") -> bytes:
        if epoch < 0:
            raise ValueError("negative epoch")
        nonce = os.urandom(12)
        aad = domain + epoch.to_bytes(8, "big") + bytes.fromhex(self.measurement)
        body = AESGCM(self._sealing_key).encrypt(nonce, state, aad)
        return epoch.to_bytes(8, "big") + nonce + body

    def unseal(self, blob: bytes, *, expected_min_epoch: int,
               domain: bytes = b"AgentTool-V5-sealed-state") -> tuple[int, bytes]:
        if len(blob) < 36:
            raise ValueError("short sealed state")
        epoch = int.from_bytes(blob[:8], "big")
        if epoch < expected_min_epoch:
            raise PermissionError("sealed-state epoch is stale relative to caller anchor")
        aad = domain + epoch.to_bytes(8, "big") + bytes.fromhex(self.measurement)
        return epoch, AESGCM(self._sealing_key).decrypt(blob[8:20], blob[20:], aad)
