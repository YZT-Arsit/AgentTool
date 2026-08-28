from __future__ import annotations

from dataclasses import dataclass

from agent_control_virtualization.ir import AgentCapsule
from privacy_kernel.control import ControlKernel, OperationClass

from .attestation import ProvisionedSession
from .verifier import VerifiedCapsule


@dataclass(frozen=True)
class TrustedKernelInventory:
    capsule_plaintext_bytes: int
    private_control_state_bytes_estimate: int
    session_key_bytes: int
    public_interfaces: tuple[str, ...]


class AttestedControlKernel:
    """Small verified runtime wrapper intended to reside inside a TEE/CVM.

    Native framework objects, compiler code, corpus tools, provider emulators,
    and experiment analysis are deliberately absent from this object.
    """

    def __init__(self, session: ProvisionedSession, capsules: list[VerifiedCapsule],
                 initial_agent_id: int,
                 provider_by_handle: dict[int, tuple[int, OperationClass]] | None = None,
                 tool_name_by_handle: dict[int, str] | None = None):
        verified = {item.capsule.logical_agent_id: item.capsule for item in capsules}
        if initial_agent_id not in verified:
            raise PermissionError("initial Agent is not in the verified capsule set")
        self._session = session
        self._verified_digests = {item.capsule_sha256 for item in capsules}
        self.control = ControlKernel(verified, initial_agent_id, provider_by_handle,
                                     tool_name_by_handle)

    def install_verified_capsule(self, capsule: VerifiedCapsule) -> None:
        self._verified_digests.add(capsule.capsule_sha256)
        self.control.install_capsule(capsule.capsule)

    @property
    def inventory(self) -> TrustedKernelInventory:
        capsule_bytes = sum(len(item.serialize()) for item in self.control.capsules.values())
        return TrustedKernelInventory(
            capsule_bytes, 4096 + capsule_bytes, 64,
            ("attest", "provision", "submit_ciphertext", "fixed_slot", "sealed_checkpoint"),
        )
