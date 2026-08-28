from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, ControlRow, Opcode
from confidential_v5.attestation import (
    AttestationStatus,
    EnterpriseAttestationPolicy,
    LocalTrustedProcessBackend,
    measure_files,
)
from confidential_v5.kernel import AttestedControlKernel
from confidential_v5.membership import LocalTrustedCatalog, capability_token
from confidential_v5.profiles import PrivacyProfile, ProfilePolicy, ToolPlacement
from confidential_v5.resolution import HierarchicalAgentResolver
from confidential_v5.verifier import CapsuleManifest, DeterministicCapsuleVerifier


ROOT = Path(__file__).resolve().parents[1]


def capsule(agent: int = 7, profile: int = 5) -> AgentCapsule:
    return AgentCapsule(agent, 91, profile, (
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 1, 1, label="return"),
    ), "pinned-source-digest")


def boot(measurement: str):
    backend = LocalTrustedProcessBackend(measurement, sealing_key=b"s" * 32)
    challenge = os.urandom(32)
    evidence = backend.attest(challenge)
    policy = EnterpriseAttestationPolicy(frozenset({measurement}), allow_local_functional_backend=True)
    session = backend.provision(evidence, X25519PrivateKey.generate(), policy, challenge)
    return backend, evidence, session


def test_local_backend_is_explicitly_not_hardware_attestation() -> None:
    measurement = measure_files(ROOT, ["confidential_v5/attestation.py", "confidential_v5/verifier.py"])
    backend, evidence, session = boot(measurement)
    assert evidence.status is AttestationStatus.LOCAL_FUNCTIONAL_EVIDENCE_ONLY
    assert evidence.hardware_signed is False
    assert backend.hardware_attestation is AttestationStatus.HARDWARE_TEE_ATTESTATION_NOT_TESTED
    assert backend.rollback_protection.startswith("NOT_IMPLEMENTED")
    assert len(session.payload_key) == len(session.transcript_key) == 32


def test_enterprise_rejects_functional_evidence_unless_explicitly_enabled() -> None:
    backend = LocalTrustedProcessBackend("ab" * 32)
    challenge = os.urandom(32)
    evidence = backend.attest(challenge)
    policy = EnterpriseAttestationPolicy(frozenset({"ab" * 32}))
    with pytest.raises(PermissionError, match="hardware-signed"):
        backend.provision(evidence, X25519PrivateKey.generate(), policy, challenge)


def test_payload_channel_is_authenticated_and_measurement_bound() -> None:
    backend, _, session = boot("11" * 32)
    protected = backend.encrypt_payload(session, b"private prompt", b"public-profile-5")
    assert b"private prompt" not in protected
    assert backend.decrypt_payload(session, protected, b"public-profile-5") == b"private prompt"
    with pytest.raises(InvalidTag):
        backend.decrypt_payload(session, protected, b"wrong-profile")


def test_sealing_detects_integrity_and_caller_anchored_staleness() -> None:
    backend, _, _ = boot("22" * 32)
    blob = backend.seal(b"private control state", epoch=8)
    assert backend.unseal(blob, expected_min_epoch=8) == (8, b"private control state")
    with pytest.raises(PermissionError, match="stale"):
        backend.unseal(blob, expected_min_epoch=9)
    changed = bytearray(blob); changed[-1] ^= 1
    with pytest.raises(InvalidTag):
        backend.unseal(bytes(changed), expected_min_epoch=8)


def test_deterministic_verifier_is_required_before_kernel_installation() -> None:
    raw = capsule().serialize()
    manifest = CapsuleManifest(hashlib.sha256(raw).hexdigest(), "official/example.py",
                               "33" * 32, "compiler-v5-dev", (5,))
    verified = DeterministicCapsuleVerifier().verify(raw, manifest)
    backend, _, session = boot("44" * 32)
    kernel = AttestedControlKernel(session, [verified], 7)
    assert kernel.control.state.logical_agent_id == 7
    assert kernel.inventory.capsule_plaintext_bytes == 1024
    bad = CapsuleManifest("00" * 32, manifest.source_path, manifest.source_sha256,
                          manifest.compiler_version, manifest.allowed_runtime_profiles)
    with pytest.raises(PermissionError, match="digest"):
        DeterministicCapsuleVerifier().verify(raw, bad)


class _Lookup:
    def __init__(self):
        self.calls: list[tuple[int | None, bool]] = []

    def retrieve(self, index: int | None, *, dummy: bool) -> AgentCapsule:
        self.calls.append((index, dummy))
        return capsule(index if index is not None else 999)


def test_strict_internal_external_resolution_has_identical_public_route_shape() -> None:
    key = b"catalog-domain-key"
    internal_token = capability_token("spreadsheet", key)
    external_token = capability_token("weather", key)
    lookup = _Lookup()
    resolver = HierarchicalAgentResolver(LocalTrustedCatalog({internal_token: 7}), lookup,
                                         lambda token: hashlib.sha256(token).digest())
    internal = resolver.resolve(internal_token, PrivacyProfile.STRICT)
    external = resolver.resolve(external_token, PrivacyProfile.STRICT)
    assert internal.public_view() == external.public_view()
    assert lookup.calls == [(7, False), (None, True)]
    assert internal.private_agent_index == 7
    assert external.external_handle is not None
    public = str(external.public_view()).lower()
    assert "external" not in public and "weather" not in public


def test_profiles_do_not_claim_cross_profile_indistinguishability() -> None:
    key = b"catalog-domain-key"
    internal = capability_token("database", key)
    external = capability_token("travel", key)
    resolver = HierarchicalAgentResolver(LocalTrustedCatalog({internal: 7}), _Lookup(), lambda x: x)
    for profile in (PrivacyProfile.CONFIDENTIAL_ENTERPRISE, PrivacyProfile.ENTERPRISE_EFFICIENT):
        assert resolver.resolve(internal, profile).public_route == "ENTERPRISE"
        assert resolver.resolve(external, profile).public_route == "EXTERNAL"


def test_strict_rejects_visible_cloud_local_tool_activation() -> None:
    strict = ProfilePolicy.for_profile(PrivacyProfile.STRICT)
    with pytest.raises(PermissionError, match="visible CLOUD_LOCAL"):
        strict.validate_tool_path(ToolPlacement.CLOUD_LOCAL,
                                  through_common_gateway=False,
                                  through_confidential_broker=False)
    strict.validate_tool_path(ToolPlacement.CLOUD_LOCAL,
                              through_common_gateway=True,
                              through_confidential_broker=False)
    strict.validate_tool_path(ToolPlacement.TEE_LOCAL,
                              through_common_gateway=False,
                              through_confidential_broker=False)


def test_enterprise_efficient_requires_declared_tool_category() -> None:
    policy = ProfilePolicy.for_profile(PrivacyProfile.ENTERPRISE_EFFICIENT)
    with pytest.raises(ValueError, match="explicit public Tool category"):
        policy.validate_tool_path(ToolPlacement.CLOUD_LOCAL,
                                  through_common_gateway=False,
                                  through_confidential_broker=False)
    policy.validate_tool_path(ToolPlacement.CLOUD_LOCAL,
                              through_common_gateway=False,
                              through_confidential_broker=False,
                              declared_category="office")
