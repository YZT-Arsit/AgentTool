"""V5 confidential-execution boundary for functional local development.

The package deliberately does not claim hardware-enclave security.  The only
backend currently shipped is ``LOCAL_TRUSTED_PROCESS_FUNCTIONAL_ONLY``; its
attestation evidence is useful for exercising bootstrap policy and key-flow
logic, not as proof against a malicious host.
"""

from .attestation import (
    AttestationEvidence,
    AttestationStatus,
    EnterpriseAttestationPolicy,
    LocalTrustedProcessBackend,
    ProvisionedSession,
)
from .profiles import PrivacyProfile, ProfilePolicy, RouteClass, ToolPlacement
from .resolution import AgentResolution, HierarchicalAgentResolver
from .verifier import CapsuleManifest, DeterministicCapsuleVerifier, VerifiedCapsule

__all__ = [
    "AgentResolution",
    "AttestationEvidence",
    "AttestationStatus",
    "CapsuleManifest",
    "DeterministicCapsuleVerifier",
    "EnterpriseAttestationPolicy",
    "HierarchicalAgentResolver",
    "LocalTrustedProcessBackend",
    "PrivacyProfile",
    "ProfilePolicy",
    "ProvisionedSession",
    "RouteClass",
    "ToolPlacement",
    "VerifiedCapsule",
]
