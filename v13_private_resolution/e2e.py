from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence, TextIO, runtime_checkable

from action_privacy_v8 import ActionKind, ProtectedActionIntent
from v11_full_scope.action_model import logical_request, protected_payload
from v11_full_scope.models import (
    CanonicalActionFamily,
    V11ActionCase,
    V11ActionOutcome,
)

from .resolution import (
    CanonicalAgentID,
    GatewayAgentDestination,
    PrivateResolutionSource,
    TwoTierPrivateAgentResolver,
)


PSI_VARIANT_REQUIRED = "RECEIVER_ONLY_PSI_OR_PRIVATE_SET_MEMBERSHIP"
PSI_OUTPUT_RECIPIENT = "TRUSTED_RUNTIME_ONLY"
ENTERPRISE_DIRECTORY_LEARNS_INTERSECTION = False

PIR_QUERY_BYTES = 2020
PIR_ANSWER_BYTES = 6592
GATEWAY_REQUEST_BYTES = 1079
GATEWAY_RESPONSE_BYTES = 800
GATEWAY_PUBLIC_CELL_COUNT = 521
REGISTRY_PUBLIC_QUERY_COUNT = 100


@dataclass(frozen=True)
class ReceiverOnlyPSIContract:
    """Required semantics for a future vetted split-domain PSI backend."""

    variant: str = PSI_VARIANT_REQUIRED
    output_recipient: str = PSI_OUTPUT_RECIPIENT
    enterprise_directory_learns_intersection: bool = (
        ENTERPRISE_DIRECTORY_LEARNS_INTERSECTION
    )
    enterprise_directory_learns_candidate_set: bool = False
    enterprise_directory_learns_selected_agent: bool = False
    enterprise_directory_learns_branch_bit: bool = False

    def validated(self) -> "ReceiverOnlyPSIContract":
        if self.variant != PSI_VARIANT_REQUIRED:
            raise ValueError("two-tier resolution requires receiver-only PSI semantics")
        if self.output_recipient != PSI_OUTPUT_RECIPIENT:
            raise ValueError("PSI output must be restricted to the trusted runtime")
        if any(
            (
                self.enterprise_directory_learns_intersection,
                self.enterprise_directory_learns_candidate_set,
                self.enterprise_directory_learns_selected_agent,
                self.enterprise_directory_learns_branch_bit,
            )
        ):
            raise ValueError("Enterprise Agent Directory received forbidden PSI output")
        return self


@dataclass(frozen=True)
class PlannerCandidateSet:
    """Trusted handoff of discrete planner candidates into resolution."""

    candidate_ids: tuple[CanonicalAgentID, ...]

    @classmethod
    def from_sequence(cls, values: Sequence[CanonicalAgentID]) -> "PlannerCandidateSet":
        # The fixed-profile resolver remains authoritative for domain, duplicate,
        # nonempty, and K-bound validation.
        return cls(tuple(values))


@dataclass(frozen=True)
class ExistingGatewayResult:
    operation_id: str
    result: str
    effect_count: int
    outcome_semantics: str

    def validated(self, expected_operation_id: str) -> "ExistingGatewayResult":
        if self.operation_id != expected_operation_id:
            raise RuntimeError("trusted Gateway returned the wrong operation ID")
        if self.effect_count < 0:
            raise ValueError("negative Gateway effect count")
        if not self.outcome_semantics:
            raise ValueError("Gateway outcome semantics are required")
        return self


GatewayResultReceiver = Callable[
    [str, GatewayAgentDestination, dict[str, object]], ExistingGatewayResult
]


@runtime_checkable
class ExistingCommonGatewaySubmission(Protocol):
    """Existing protected action ingress used by both private target classes."""

    def handoff(self, destination: GatewayAgentDestination) -> None: ...

    def submit_staged(self, intent: ProtectedActionIntent) -> ExistingGatewayResult: ...

    def public_ingress_view(self) -> dict[str, object]: ...


def _canonical_agent_service_action(
    destination: GatewayAgentDestination,
    intent: ProtectedActionIntent,
) -> dict[str, object]:
    """Build the existing private ``SUBMIT_RESOLVED_ACTION`` Agent payload."""

    descriptor = destination.descriptor.validated()
    if descriptor.agent_id != destination.canonical_agent_id:
        raise ValueError("resolved target and descriptor Agent IDs disagree")
    if intent.action_kind is not ActionKind.AGENT_SERVICE:
        raise ValueError("two-tier Agent execution requires AGENT_SERVICE")
    if intent.capability not in descriptor.capability_ids:
        raise PermissionError("resolved Agent does not authorize the requested capability")
    service = descriptor.agent_service
    if service is None:
        raise LookupError("resolved Agent descriptor has no Agent-service route")
    service.validated()
    if not destination.private_execution_handle:
        raise ValueError("resolved Agent target has no private execution handle")
    return {
        "operation_id": intent.operation_id,
        "action_kind": "REAL_AGENT_SERVICE",
        # The Enterprise Agent Directory may bind a deployment-specific handle
        # that differs from the global descriptor's route. Both remain private
        # trusted-Gateway routing state and use the same control ABI.
        "route_handle": destination.private_execution_handle,
        "effect_semantics": service.effect_semantics.value,
        "policy_id": service.policy_id,
        # This matches the existing Go encoding/json representation for []byte.
        "protected_arguments": base64.b64encode(intent.protected_arguments).decode(
            "ascii"
        ),
    }


class ExistingGatewayControlChannelAdapter:
    """Narrow composition adapter for the frozen Gateway control ingress.

    Both source classes stage private routing state here and emit the same
    ``SUBMIT_RESOLVED_ACTION`` control message on the already-established
    trusted Gateway session. This class creates no network connection and has
    no endpoint- or source-class-specific public method.
    """

    private_control_message_type = "SUBMIT_RESOLVED_ACTION"
    direct_tee_to_agent_connections = 0

    def __init__(self, writer: TextIO, result_receiver: GatewayResultReceiver):
        self._writer = writer
        self._result_receiver = result_receiver
        self._staged: GatewayAgentDestination | None = None
        self.submitted_private_actions: list[dict[str, object]] = []
        self.submitted_private_targets: list[GatewayAgentDestination] = []

    def handoff(self, destination: GatewayAgentDestination) -> None:
        if self._staged is not None:
            raise RuntimeError("a private Agent target is already staged")
        destination.descriptor.validated()
        self._staged = destination

    def submit_staged(self, intent: ProtectedActionIntent) -> ExistingGatewayResult:
        destination = self._staged
        if destination is None:
            raise RuntimeError("no resolved Agent target is staged")
        try:
            action = _canonical_agent_service_action(destination, intent)
            message = {
                "type": self.private_control_message_type,
                "action": action,
            }
            self._writer.write(json.dumps(message, separators=(",", ":")) + "\n")
            self._writer.flush()
            self.submitted_private_targets.append(destination)
            self.submitted_private_actions.append(action)
            return self._result_receiver(
                intent.operation_id, destination, action
            ).validated(intent.operation_id)
        finally:
            self._staged = None

    @staticmethod
    def public_ingress_view() -> dict[str, object]:
        return {
            "gateway_public_ingress": "V4R8_COMMON_TRUSTED_GATEWAY",
            "gateway_public_cell_count": GATEWAY_PUBLIC_CELL_COUNT,
            "gateway_request_bytes": GATEWAY_REQUEST_BYTES,
            "gateway_response_bytes": GATEWAY_RESPONSE_BYTES,
        }


def structural_resolution_projection(
    public_resolution: dict[str, object],
    gateway_public_ingress: dict[str, object],
) -> dict[str, object]:
    """Allowlisted structural view V=(Q_PSI,Q_PIR,M), excluding timing."""

    required = {
        "profile_identifier",
        "candidate_batch_k",
        "enterprise_cardinality_policy",
        "enterprise_cardinality_bound",
        "request_message_size_class",
        "response_message_size_class",
        "psi_slot_count",
        "pir_slot_count",
        "gateway_public_path_count",
        "gateway_public_cell_count",
        "registry_public_query_count",
    }
    if set(public_resolution) != required:
        raise ValueError("unexpected field entered the public resolution view")
    expected_gateway = ExistingGatewayControlChannelAdapter.public_ingress_view()
    if gateway_public_ingress != expected_gateway:
        raise ValueError("Gateway ingress differs from the frozen common boundary")
    if (
        public_resolution["psi_slot_count"] != 1
        or public_resolution["pir_slot_count"] != 1
        or public_resolution["gateway_public_path_count"] != 1
        or public_resolution["gateway_public_cell_count"]
        != gateway_public_ingress["gateway_public_cell_count"]
        or public_resolution["registry_public_query_count"]
        != REGISTRY_PUBLIC_QUERY_COUNT
    ):
        raise ValueError("two-tier resolution changed a fixed public count")
    return {
        "Q_PSI": {
            "profile_identifier": public_resolution["profile_identifier"],
            "candidate_batch_k": public_resolution["candidate_batch_k"],
            "enterprise_cardinality_policy": public_resolution[
                "enterprise_cardinality_policy"
            ],
            "enterprise_cardinality_bound": public_resolution[
                "enterprise_cardinality_bound"
            ],
            "request_message_size_class": public_resolution[
                "request_message_size_class"
            ],
            "response_message_size_class": public_resolution[
                "response_message_size_class"
            ],
            "slot_count": public_resolution["psi_slot_count"],
        },
        "Q_PIR": {
            "slot_count": public_resolution["pir_slot_count"],
            "query_bytes": PIR_QUERY_BYTES,
            "answer_bytes": PIR_ANSWER_BYTES,
            "public_query_count": public_resolution["registry_public_query_count"],
        },
        "M": {
            **gateway_public_ingress,
            "gateway_public_path_count": public_resolution[
                "gateway_public_path_count"
            ],
        },
    }


class TwoTierFrameworkGatewayComposition:
    """Planner candidates -> two-tier resolver -> frozen Gateway ingress."""

    def __init__(
        self,
        resolver: TwoTierPrivateAgentResolver,
        gateway: ExistingCommonGatewaySubmission,
        candidates_by_operation: dict[str, PlannerCandidateSet],
        *,
        psi_contract: ReceiverOnlyPSIContract | None = None,
    ):
        if resolver.gateway is not gateway:
            raise ValueError("resolver and composition must share one Gateway adapter")
        self.resolver = resolver
        self.gateway = gateway
        self.candidates_by_operation = dict(candidates_by_operation)
        self.psi_contract = (psi_contract or ReceiverOnlyPSIContract()).validated()
        self.executed_operation_ids: list[str] = []

    def __call__(
        self, case: V11ActionCase, arguments: dict[str, Any]
    ) -> V11ActionOutcome:
        case.validate()
        if case.action_family is not CanonicalActionFamily.AGENT_SERVICE:
            raise ValueError("two-tier framework composition accepts Agent services")
        if arguments != case.argument_schema.validate_values(case.arguments):
            raise AssertionError("framework changed structured arguments")
        try:
            candidates = self.candidates_by_operation[case.operation_id]
        except KeyError as exc:
            raise LookupError("planner candidate set is absent") from exc
        resolution = self.resolver.resolve_and_handoff(
            case.operation_id, candidates.candidate_ids
        )
        intent = ProtectedActionIntent(
            capability=case.capability,
            protected_arguments=protected_payload(case),
            session_id="v13b-two-tier-development",
            operation_id=case.operation_id,
            action_kind=ActionKind.AGENT_SERVICE,
        )
        gateway_result = self.gateway.submit_staged(intent)
        self.executed_operation_ids.append(case.operation_id)
        public_projection = structural_resolution_projection(
            resolution.public_view(), self.gateway.public_ingress_view()
        )
        return V11ActionOutcome(
            result=gateway_result.result,
            effect_count=gateway_result.effect_count,
            outcome_semantics=gateway_result.outcome_semantics,
            provider_visible_logical_request=logical_request(case),
            evidence={
                "public_structural_projection": public_projection,
                "private_resolution": {
                    "selected_agent_id": resolution.private.selected_agent_id,
                    "source_class": resolution.private.source.value,
                    "pir_behavior": resolution.private.pir_behavior.value,
                    "descriptor": resolution.private.destination.descriptor,
                    "private_execution_handle": (
                        resolution.private.destination.private_execution_handle
                    ),
                },
                "gateway_private_control_message_type": (
                    ExistingGatewayControlChannelAdapter.private_control_message_type
                ),
                "silent_loss": False,
            },
        )


def execution_identity_audit() -> dict[str, object]:
    """Mechanical classification under the unchanged canonical observer."""

    return {
        "direct_tee_to_enterprise_agent_connections": 0,
        "composition_network_clients": 0,
        "gateway_public_ingress": "V4R8_COMMON_TRUSTED_GATEWAY",
        "source_class_in_public_projection": False,
        "private_route_in_public_projection": False,
        "classification": "OUTSIDE_FROZEN_OBSERVER_AFTER_COMMON_GATEWAY",
        "reason": (
            "The frozen O_agentcloud view terminates at the common trusted "
            "Gateway ingress and explicitly excludes independently observed "
            "downstream provider traffic. The composition creates no direct "
            "TEE-to-Agent connection. A deployment in which the same cloud "
            "operator can observe post-Gateway endpoint, process, container, "
            "or connection identity is outside that frozen boundary and would "
            "invalidate the identity-hiding claim."
        ),
    }
