from __future__ import annotations

import hashlib
from dataclasses import dataclass

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, Opcode


@dataclass(frozen=True)
class CapsuleManifest:
    capsule_sha256: str
    source_path: str
    source_sha256: str
    compiler_version: str
    allowed_runtime_profiles: tuple[int, ...]
    max_states: int = 64
    max_transitions: int = 30


@dataclass(frozen=True)
class VerifiedCapsule:
    capsule: AgentCapsule
    capsule_sha256: str
    source_path: str
    compiler_version: str


class DeterministicCapsuleVerifier:
    """Runtime verifier; compilation/classification remain outside the TCB."""

    allowed_opcodes = frozenset({
        Opcode.NOOP, Opcode.LLM, Opcode.TOOL, Opcode.HANDOFF, Opcode.STATE_GET,
        Opcode.STATE_SET, Opcode.POLICY, Opcode.RETURN, Opcode.BRANCH,
    })

    def verify(self, payload: bytes, manifest: CapsuleManifest) -> VerifiedCapsule:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != manifest.capsule_sha256:
            raise PermissionError("capsule digest does not match signed build manifest")
        capsule = AgentCapsule.deserialize(payload)
        if capsule.runtime_profile not in manifest.allowed_runtime_profiles:
            raise PermissionError("capsule runtime profile is not approved")
        if capsule.state_count > manifest.max_states or capsule.transition_count > manifest.max_transitions:
            raise PermissionError("capsule exceeds verified public bounds")
        if any(row.opcode not in self.allowed_opcodes for row in capsule.rows):
            raise PermissionError("capsule contains an unsupported opcode")
        pairs = {(row.current_state, row.event) for row in capsule.rows}
        if len(pairs) != len(capsule.rows):
            raise PermissionError("capsule transition relation is nondeterministic")
        states = {row.current_state for row in capsule.rows} | {row.next_state for row in capsule.rows}
        if 0 not in states:
            raise PermissionError("capsule has no entry state")
        if not any(row.opcode is Opcode.RETURN for row in capsule.rows):
            raise PermissionError("capsule has no bounded return transition")
        for row in capsule.rows:
            if row.opcode is Opcode.BRANCH and row.flags not in states:
                raise PermissionError("declarative branch targets an unknown state")
            if row.event not in ControlEvent:
                raise PermissionError("invalid control event")
        return VerifiedCapsule(capsule, digest, manifest.source_path, manifest.compiler_version)
