from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Iterable, Protocol, Sequence, runtime_checkable

from action_privacy_v8 import AgentDescriptorV7


CanonicalAgentID = int

CANDIDATE_BATCH_K = 8
ENTERPRISE_CARDINALITY_BOUND = 1024
_DUMMY_IDENTIFIER_BASE = 1 << 63
_DUMMY_IDENTIFIER_LIMIT = 1 << 64
PSI_CRYPTO_BACKEND_STATUS = "NOT_CRYPTOGRAPHICALLY_INSTANTIATED"
PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE = "PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE"


class EnterpriseCardinalityPolicy(StrEnum):
    PUBLIC = "PUBLIC"
    PADDED = "PADDED"


class PIRSlotBehavior(StrEnum):
    PADDING_QUERY = "PADDING_QUERY"
    REAL_QUERY = "REAL_QUERY"


class PrivateResolutionSource(StrEnum):
    ENTERPRISE_DEPLOYED_AGENT = "ENTERPRISE_DEPLOYED_AGENT"
    GLOBAL_AGENT_LIBRARY = "GLOBAL_AGENT_LIBRARY"


@dataclass(frozen=True)
class PSIProfile:
    """Public, non-secret parameters for one availability-resolution slot."""

    profile_identifier: str
    candidate_batch_k: int
    enterprise_cardinality_policy: EnterpriseCardinalityPolicy
    enterprise_cardinality_bound: int
    request_message_size_class: str
    response_message_size_class: str
    public_psi_slots_per_resolution: int = 1
    public_pir_slots_per_resolution: int = 1

    def validated(self) -> "PSIProfile":
        if not self.profile_identifier:
            raise ValueError("PSI profile identifier is required")
        if self.candidate_batch_k <= 0:
            raise ValueError("candidate batch K must be positive")
        if self.enterprise_cardinality_policy is EnterpriseCardinalityPolicy.PADDED:
            if self.enterprise_cardinality_bound <= 0:
                raise ValueError("padded enterprise cardinality requires a public bound")
        elif self.enterprise_cardinality_bound < 0:
            raise ValueError("enterprise cardinality cannot be negative")
        if not self.request_message_size_class or not self.response_message_size_class:
            raise ValueError("fixed PSI request/response size classes are required")
        if self.public_psi_slots_per_resolution != 1:
            raise ValueError("two-tier resolution requires exactly one public PSI slot")
        if self.public_pir_slots_per_resolution != 1:
            raise ValueError("two-tier resolution requires exactly one public PIR slot")
        return self

    def public_view(self) -> dict[str, object]:
        self.validated()
        return {
            "profile_identifier": self.profile_identifier,
            "candidate_batch_k": self.candidate_batch_k,
            "enterprise_cardinality_policy": self.enterprise_cardinality_policy.value,
            "enterprise_cardinality_bound": self.enterprise_cardinality_bound,
            "request_message_size_class": self.request_message_size_class,
            "response_message_size_class": self.response_message_size_class,
            "psi_slot_count": self.public_psi_slots_per_resolution,
            "pir_slot_count": self.public_pir_slots_per_resolution,
        }


def default_psi_profile() -> PSIProfile:
    return PSIProfile(
        profile_identifier="TWO-TIER-PRIVATE-AGENT-RESOLUTION-K8-E1024",
        candidate_batch_k=CANDIDATE_BATCH_K,
        enterprise_cardinality_policy=EnterpriseCardinalityPolicy.PADDED,
        enterprise_cardinality_bound=ENTERPRISE_CARDINALITY_BOUND,
        request_message_size_class="PSI-REQUEST-K8-E1024",
        response_message_size_class="PSI-RESPONSE-K8-E1024",
    ).validated()


def _validated_agent_id(value: int) -> CanonicalAgentID:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("canonical Agent ID must be an integer")
    if value < 0 or value >= _DUMMY_IDENTIFIER_BASE:
        raise ValueError("canonical Agent ID is outside the supported stable-ID domain")
    return value


@dataclass(frozen=True)
class EnterpriseAgentRecord:
    canonical_agent_id: CanonicalAgentID
    private_execution_handle: str
    descriptor: AgentDescriptorV7
    descriptor_digest: str | None = None
    descriptor_version: int | None = None

    def validated(self) -> "EnterpriseAgentRecord":
        agent_id = _validated_agent_id(self.canonical_agent_id)
        self.descriptor.validated()
        if self.descriptor.agent_id != agent_id:
            raise ValueError("enterprise record and descriptor Agent IDs disagree")
        if not self.private_execution_handle:
            raise ValueError("enterprise execution handle is required")
        if self.descriptor_digest is not None and not self.descriptor_digest:
            raise ValueError("empty descriptor digest")
        if self.descriptor_version is not None and self.descriptor_version < 0:
            raise ValueError("negative descriptor version")
        return self


class EnterpriseAgentDirectory:
    """Private split-domain inventory owned by the enterprise PSI endpoint."""

    def __init__(self, records: Iterable[EnterpriseAgentRecord]):
        self._records: dict[CanonicalAgentID, EnterpriseAgentRecord] = {}
        for record in records:
            record = record.validated()
            if record.canonical_agent_id in self._records:
                raise ValueError("duplicate enterprise Agent ID")
            self._records[record.canonical_agent_id] = record

    def validate_profile(self, profile: PSIProfile) -> None:
        profile.validated()
        if (
            profile.enterprise_cardinality_policy is EnterpriseCardinalityPolicy.PADDED
            and len(self._records) > profile.enterprise_cardinality_bound
        ):
            raise ValueError("enterprise inventory exceeds its public padding bound")

    def private_lookup(self, agent_id: CanonicalAgentID) -> EnterpriseAgentRecord | None:
        return self._records.get(_validated_agent_id(agent_id))

    def private_identifier_inventory(self, profile: PSIProfile) -> tuple[int, ...]:
        """Materialize the mock-only padded inventory for functional tests.

        A real PSI backend owns its server-side encoding and padding.  Returning
        raw IDs here is deliberately limited to the non-cryptographic mock.
        """

        self.validate_profile(profile)
        identifiers = list(self._records)
        if profile.enterprise_cardinality_policy is EnterpriseCardinalityPolicy.PADDED:
            identifiers.extend(
                _DUMMY_IDENTIFIER_BASE + offset
                for offset in range(profile.enterprise_cardinality_bound - len(identifiers))
            )
        return tuple(identifiers)

    @property
    def private_record_count(self) -> int:
        return len(self._records)


@dataclass(frozen=True)
class PrivateAvailabilityResult:
    matched_ids: tuple[CanonicalAgentID, ...]
    enterprise_hit: bool
    diagnostic_status: str
    backend: str
    cryptographic_status: str


@runtime_checkable
class PrivateAgentAvailabilityResolver(Protocol):
    profile: PSIProfile

    def resolve(self, candidate_ids: Sequence[CanonicalAgentID]) -> "AvailabilityResolution": ...


@runtime_checkable
class PSIBackend(Protocol):
    backend_name: str
    cryptographic_status: str

    def intersect(
        self,
        padded_candidate_ids: tuple[int, ...],
        profile: PSIProfile,
    ) -> tuple[CanonicalAgentID, ...]: ...


class DeterministicMockPSIBackend:
    """Functional-only raw-set intersection; never a cryptographic PSI claim."""

    backend_name = "DETERMINISTIC_MOCK_PSI_FUNCTIONAL_ONLY"
    cryptographic_status = PSI_CRYPTO_BACKEND_STATUS

    def __init__(self, directory: EnterpriseAgentDirectory):
        self.directory = directory
        self.calls: list[tuple[int, ...]] = []
        self.server_inventory_sizes: list[int] = []

    def intersect(
        self,
        padded_candidate_ids: tuple[int, ...],
        profile: PSIProfile,
    ) -> tuple[CanonicalAgentID, ...]:
        # This intentionally exposes raw IDs inside a deterministic test double.
        # It cannot be deployed across the split-domain trust boundary.
        self.calls.append(padded_candidate_ids)
        server_inventory = set(self.directory.private_identifier_inventory(profile))
        self.server_inventory_sizes.append(len(server_inventory))
        return tuple(
            value
            for value in padded_candidate_ids
            if value < _DUMMY_IDENTIFIER_BASE and value in server_inventory
        )


class FailingMockPSIBackend:
    backend_name = "FAILING_MOCK_PSI_FUNCTIONAL_ONLY"
    cryptographic_status = PSI_CRYPTO_BACKEND_STATUS

    def __init__(self, message: str = "synthetic PSI failure"):
        self.message = message
        self.calls = 0

    def intersect(
        self,
        padded_candidate_ids: tuple[int, ...],
        profile: PSIProfile,
    ) -> tuple[CanonicalAgentID, ...]:
        del padded_candidate_ids, profile
        self.calls += 1
        raise RuntimeError(self.message)


@dataclass(frozen=True)
class AvailabilityResolution:
    candidate_ids: tuple[CanonicalAgentID, ...]
    padded_candidate_ids: tuple[int, ...]
    private_result: PrivateAvailabilityResult


class FixedProfilePrivateAgentAvailabilityResolver:
    """Pads planner candidates and invokes exactly one configured PSI slot."""

    def __init__(
        self,
        backend: PSIBackend,
        profile: PSIProfile | None = None,
        *,
        dummy_identifier_source: Callable[[], int] | None = None,
    ):
        self.backend = backend
        self.profile = (profile or default_psi_profile()).validated()
        self._dummy_identifier_source = dummy_identifier_source or (
            lambda: _DUMMY_IDENTIFIER_BASE
            + secrets.randbelow(_DUMMY_IDENTIFIER_LIMIT - _DUMMY_IDENTIFIER_BASE)
        )

    def _normalize(self, candidate_ids: Sequence[CanonicalAgentID]) -> tuple[int, ...]:
        values = tuple(_validated_agent_id(value) for value in candidate_ids)
        if not values:
            raise ValueError("planner candidate set must not be empty")
        if len(values) > self.profile.candidate_batch_k:
            raise ValueError("planner candidate set exceeds public candidate batch K")
        if len(set(values)) != len(values):
            raise ValueError("planner candidate set contains duplicate Agent IDs")
        return values

    def _pad(self, values: tuple[int, ...]) -> tuple[int, ...]:
        padded = list(values)
        used = set(values)
        while len(padded) < self.profile.candidate_batch_k:
            dummy = self._dummy_identifier_source()
            if (
                isinstance(dummy, bool)
                or not isinstance(dummy, int)
                or not _DUMMY_IDENTIFIER_BASE <= dummy < _DUMMY_IDENTIFIER_LIMIT
            ):
                raise ValueError("dummy candidate identifier is outside the reserved domain")
            if dummy not in used:
                padded.append(dummy)
                used.add(dummy)
        return tuple(padded)

    def resolve(self, candidate_ids: Sequence[CanonicalAgentID]) -> AvailabilityResolution:
        values = self._normalize(candidate_ids)
        padded = self._pad(values)
        matched = tuple(self.backend.intersect(padded, self.profile))
        if len(set(matched)) != len(matched) or any(value not in values for value in matched):
            raise RuntimeError("PSI backend returned an invalid private intersection")
        ordered = tuple(value for value in values if value in set(matched))
        return AvailabilityResolution(
            candidate_ids=values,
            padded_candidate_ids=padded,
            private_result=PrivateAvailabilityResult(
                matched_ids=ordered,
                enterprise_hit=bool(ordered),
                diagnostic_status="PSI_SLOT_COMPLETE",
                backend=self.backend.backend_name,
                cryptographic_status=self.backend.cryptographic_status,
            ),
        )


@dataclass(frozen=True)
class PIRSlotResult:
    behavior: PIRSlotBehavior
    descriptor: AgentDescriptorV7 | None
    public_slot_count: int = 1


@runtime_checkable
class PIRAgentLibrarySlot(Protocol):
    def execute_slot(
        self, operation_id: str, requested_agent_id: CanonicalAgentID | None
    ) -> PIRSlotResult: ...


class ExistingSimplePIRSlotAdapter:
    """Thin adapter to the existing fixed-schedule SimplePIR resolver.

    Passing ``None`` enqueues the existing reserved dummy row; passing an Agent
    ID enqueues the real descriptor row.  The existing cover scheduler remains
    responsible for the public query opportunity and its fixed wire shape.
    """

    def __init__(self, online_simplepir_resolver: object):
        self._resolver = online_simplepir_resolver

    def execute_slot(
        self, operation_id: str, requested_agent_id: CanonicalAgentID | None
    ) -> PIRSlotResult:
        if requested_agent_id is None:
            dummy_index = int(getattr(self._resolver, "cover_dummy_index"))
            getattr(self._resolver, "query")(f"{operation_id}:library-padding", dummy_index)
            return PIRSlotResult(PIRSlotBehavior.PADDING_QUERY, None)
        agent_id = _validated_agent_id(requested_agent_id)
        descriptor = getattr(self._resolver, "resolve_descriptor")(
            operation_id, agent_id
        )
        if not isinstance(descriptor, AgentDescriptorV7):
            raise TypeError("SimplePIR adapter did not recover AgentDescriptorV7")
        return PIRSlotResult(PIRSlotBehavior.REAL_QUERY, descriptor.validated())


class MockPIRSlotBackend:
    """Deterministic adapter double; the actual PIR primitive remains unchanged."""

    def __init__(self, library: dict[CanonicalAgentID, AgentDescriptorV7]):
        self.library = {key: value.validated() for key, value in library.items()}
        self.calls: list[tuple[str, CanonicalAgentID | None]] = []

    def execute_slot(
        self, operation_id: str, requested_agent_id: CanonicalAgentID | None
    ) -> PIRSlotResult:
        self.calls.append((operation_id, requested_agent_id))
        if requested_agent_id is None:
            return PIRSlotResult(PIRSlotBehavior.PADDING_QUERY, None)
        agent_id = _validated_agent_id(requested_agent_id)
        try:
            descriptor = self.library[agent_id]
        except KeyError as exc:
            raise LookupError("global Agent Library row is unavailable") from exc
        return PIRSlotResult(PIRSlotBehavior.REAL_QUERY, descriptor)


@dataclass(frozen=True)
class GatewayAgentDestination:
    canonical_agent_id: CanonicalAgentID
    private_execution_handle: str
    descriptor: AgentDescriptorV7
    source: PrivateResolutionSource


@runtime_checkable
class TrustedGatewayHandoff(Protocol):
    def handoff(self, destination: GatewayAgentDestination) -> None: ...


class RecordingTrustedGateway:
    """Functional test double for the existing trusted Gateway abstraction."""

    def __init__(self):
        self.destinations: list[GatewayAgentDestination] = []

    def handoff(self, destination: GatewayAgentDestination) -> None:
        destination.descriptor.validated()
        self.destinations.append(destination)


@dataclass(frozen=True)
class PublicAgentResolutionTranscript:
    profile: PSIProfile
    psi_slot_count: int
    pir_slot_count: int
    gateway_public_path_count: int = 1
    gateway_public_cell_count: int = 521
    registry_public_query_count: int = 100

    def public_view(self) -> dict[str, object]:
        return {
            **self.profile.public_view(),
            "psi_slot_count": self.psi_slot_count,
            "pir_slot_count": self.pir_slot_count,
            "gateway_public_path_count": self.gateway_public_path_count,
            "gateway_public_cell_count": self.gateway_public_cell_count,
            "registry_public_query_count": self.registry_public_query_count,
        }


@dataclass(frozen=True)
class PrivateTwoTierResolution:
    candidate_ids: tuple[CanonicalAgentID, ...]
    matched_ids: tuple[CanonicalAgentID, ...]
    selected_agent_id: CanonicalAgentID
    source: PrivateResolutionSource
    enterprise_hit: bool
    pir_behavior: PIRSlotBehavior
    destination: GatewayAgentDestination


@dataclass(frozen=True)
class TwoTierResolutionOutcome:
    private: PrivateTwoTierResolution
    public: PublicAgentResolutionTranscript

    def public_view(self) -> dict[str, object]:
        return self.public.public_view()


class TwoTierResolutionError(RuntimeError):
    def __init__(self, message: str, public: PublicAgentResolutionTranscript):
        super().__init__(message)
        self.public = public


class TwoTierPrivateAgentResolver:
    """Compose one PSI slot, one PIR slot, and one trusted Gateway handoff."""

    selector_policy = "FIRST_PLANNER_ORDER_MATCH_ELSE_FIRST_CANDIDATE"

    def __init__(
        self,
        availability: PrivateAgentAvailabilityResolver,
        enterprise_directory: EnterpriseAgentDirectory,
        library_pir: PIRAgentLibrarySlot,
        gateway: TrustedGatewayHandoff,
    ):
        self.availability = availability
        self.enterprise_directory = enterprise_directory
        self.library_pir = library_pir
        self.gateway = gateway
        self.enterprise_directory.validate_profile(availability.profile)

    def _public(self) -> PublicAgentResolutionTranscript:
        profile = self.availability.profile
        return PublicAgentResolutionTranscript(
            profile=profile,
            psi_slot_count=profile.public_psi_slots_per_resolution,
            pir_slot_count=profile.public_pir_slots_per_resolution,
        )

    @staticmethod
    def _library_handle(descriptor: AgentDescriptorV7) -> str:
        if descriptor.agent_service is not None:
            return descriptor.agent_service.route_handle
        return f"global-agent-descriptor:{descriptor.agent_id}"

    def resolve_and_handoff(
        self,
        operation_id: str,
        candidate_ids: Sequence[CanonicalAgentID],
    ) -> TwoTierResolutionOutcome:
        if not operation_id:
            raise ValueError("operation ID is required")
        try:
            availability = self.availability.resolve(candidate_ids)
        except Exception as exc:
            # A PSI error cannot silently select the external path.  The fixed
            # PIR slot is still consumed with padding before failing closed.
            try:
                self.library_pir.execute_slot(operation_id, None)
            except Exception as pir_exc:
                raise TwoTierResolutionError(
                    f"PSI and fixed padding PIR slots failed: {exc}; {pir_exc}",
                    self._public(),
                ) from pir_exc
            raise TwoTierResolutionError(
                f"PSI availability resolution failed closed: {exc}",
                self._public(),
            ) from exc

        matched = availability.private_result.matched_ids
        if matched:
            selected_id = matched[0]
            record = self.enterprise_directory.private_lookup(selected_id)
            if record is None:
                raise RuntimeError("PSI match is absent from Enterprise Agent Directory")
            pir = self.library_pir.execute_slot(operation_id, None)
            if pir.behavior is not PIRSlotBehavior.PADDING_QUERY:
                raise RuntimeError("enterprise hit did not consume a padding PIR slot")
            destination = GatewayAgentDestination(
                canonical_agent_id=selected_id,
                private_execution_handle=record.private_execution_handle,
                descriptor=record.descriptor,
                source=PrivateResolutionSource.ENTERPRISE_DEPLOYED_AGENT,
            )
        else:
            selected_id = availability.candidate_ids[0]
            pir = self.library_pir.execute_slot(operation_id, selected_id)
            if pir.behavior is not PIRSlotBehavior.REAL_QUERY or pir.descriptor is None:
                raise RuntimeError("library fallback did not recover a real descriptor")
            destination = GatewayAgentDestination(
                canonical_agent_id=selected_id,
                private_execution_handle=self._library_handle(pir.descriptor),
                descriptor=pir.descriptor,
                source=PrivateResolutionSource.GLOBAL_AGENT_LIBRARY,
            )
        if pir.public_slot_count != 1:
            raise RuntimeError("PIR adapter changed the fixed public slot count")
        self.gateway.handoff(destination)
        return TwoTierResolutionOutcome(
            private=PrivateTwoTierResolution(
                candidate_ids=availability.candidate_ids,
                matched_ids=matched,
                selected_agent_id=selected_id,
                source=destination.source,
                enterprise_hit=bool(matched),
                pir_behavior=pir.behavior,
                destination=destination,
            ),
            public=self._public(),
        )
