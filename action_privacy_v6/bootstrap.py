from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from confidential_v5.attestation import (EnterpriseAttestationPolicy,
                                         LocalTrustedProcessBackend)


@dataclass(frozen=True)
class V6ProvisionedKeys:
    descriptor_key: bytes
    gateway_key: bytes
    session_id: str
    hardware_attestation: str


def bootstrap_local_v6(measurement: str) -> V6ProvisionedKeys:
    """Exercise the bootstrap API without claiming hardware attestation."""
    runtime = LocalTrustedProcessBackend(measurement)
    challenge = os.urandom(32)
    evidence = runtime.attest(challenge)
    enterprise = X25519PrivateKey.generate()
    session = runtime.provision(
        evidence, enterprise,
        EnterpriseAttestationPolicy(frozenset({measurement}), allow_local_functional_backend=True),
        challenge,
    )
    material = HKDF(algorithm=hashes.SHA256(), length=64, salt=challenge,
                    info=b"AgentTool-V6-TrustedActionModule-keys").derive(
                        session.payload_key + session.transcript_key)
    return V6ProvisionedKeys(material[:32], material[32:], session.session_id, "NOT_TESTED")
