from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from agent_control_virtualization.ir import AgentCapsule

from .membership import MembershipBackend
from .profiles import PrivacyProfile, ProfilePolicy, RouteClass


class CapsuleLookup(Protocol):
    def retrieve(self, index: int | None, *, dummy: bool) -> AgentCapsule: ...


@dataclass(frozen=True)
class AgentResolution:
    profile: PrivacyProfile
    private_route: RouteClass
    private_agent_index: int | None
    capsule: AgentCapsule | None
    external_handle: bytes | None
    public_route: str
    pir_operation: str
    gateway_operation: str
    membership_backend: str
    cryptographic_membership_status: str

    def public_view(self) -> dict[str, str]:
        return {
            "profile": self.profile.value,
            "route": self.public_route,
            "pir_operation": self.pir_operation,
            "gateway_operation": self.gateway_operation,
            "outer_destination": "CommonActionGatewayV2",
        }


class HierarchicalAgentResolver:
    """Runs inside the confidential boundary; no private field enters public_view."""

    def __init__(self, membership: MembershipBackend, lookup: CapsuleLookup,
                 external_discovery: Callable[[bytes], bytes]):
        self._membership = membership
        self._lookup = lookup
        self._external_discovery = external_discovery

    def resolve(self, capability: bytes, profile: PrivacyProfile) -> AgentResolution:
        policy = ProfilePolicy.for_profile(profile)
        member = self._membership.lookup(capability)
        if member.found:
            if member.private_agent_index is None:
                raise AssertionError("membership hit omitted private Agent index")
            capsule = self._lookup.retrieve(member.private_agent_index, dummy=False)
            route, external = RouteClass.ENTERPRISE, None
            pir_operation = "FIXED_PRIVATE_LOOKUP"
        else:
            # STRICT still consumes the public PIR slot using a reserved dummy
            # row.  The actual external handle stays inside the TEE/Gateway.
            capsule = self._lookup.retrieve(None, dummy=True) if policy.common_outer_route else None
            external = self._external_discovery(capability)
            route = RouteClass.EXTERNAL
            pir_operation = "FIXED_PRIVATE_LOOKUP" if policy.common_outer_route else "NONE_PUBLIC_ROUTE"
        gateway_operation = "FIXED_COMMON_GATEWAY_SLOT" if policy.common_outer_route else route.value
        return AgentResolution(
            profile, route, member.private_agent_index, capsule, external,
            policy.public_route(route), pir_operation, gateway_operation,
            member.backend, member.cryptographic_privacy,
        )
