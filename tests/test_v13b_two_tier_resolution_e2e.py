from __future__ import annotations

import ast
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from action_privacy_v8 import (
    AgentDescriptorV7,
    AgentServiceRouteDescriptor,
    EffectSemantics,
    PlacementClass,
)
from v11_full_scope.models import (
    AgentServiceSubtype,
    ArgumentField,
    ArgumentSchema,
    CanonicalActionFamily,
    V11ActionCase,
)
from v11_online.frameworks import run_online_framework_workflow
from v12_timing.profile import duplex_response_anchor_p10_profile
from v13_private_resolution.e2e import (
    ENTERPRISE_DIRECTORY_LEARNS_INTERSECTION,
    GATEWAY_PUBLIC_CELL_COUNT,
    GATEWAY_REQUEST_BYTES,
    GATEWAY_RESPONSE_BYTES,
    PIR_ANSWER_BYTES,
    PIR_QUERY_BYTES,
    PSI_OUTPUT_RECIPIENT,
    PSI_VARIANT_REQUIRED,
    ExistingGatewayControlChannelAdapter,
    ExistingGatewayResult,
    PlannerCandidateSet,
    ReceiverOnlyPSIContract,
    TwoTierFrameworkGatewayComposition,
    execution_identity_audit,
)
from v13_private_resolution.resolution import (
    DeterministicMockPSIBackend,
    EnterpriseAgentDirectory,
    EnterpriseAgentRecord,
    FixedProfilePrivateAgentAvailabilityResolver,
    MockPIRSlotBackend,
    PIRSlotBehavior,
    PrivateResolutionSource,
    TwoTierPrivateAgentResolver,
    default_psi_profile,
)


FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


@dataclass(frozen=True)
class IntegrationCase:
    name: str
    candidates: tuple[int, ...]
    enterprise_ids: tuple[int, ...]
    selected_id: int
    source: PrivateResolutionSource
    pir_behavior: PIRSlotBehavior


CASES = (
    IntegrationCase(
        "ENTERPRISE_HIT_SINGLETON",
        (7,),
        (7,),
        7,
        PrivateResolutionSource.ENTERPRISE_DEPLOYED_AGENT,
        PIRSlotBehavior.PADDING_QUERY,
    ),
    IntegrationCase(
        "ENTERPRISE_HIT_MULTI_CANDIDATE",
        (6, 7, 8),
        (7,),
        7,
        PrivateResolutionSource.ENTERPRISE_DEPLOYED_AGENT,
        PIRSlotBehavior.PADDING_QUERY,
    ),
    IntegrationCase(
        "LIBRARY_FALLBACK_SINGLETON",
        (7,),
        (),
        7,
        PrivateResolutionSource.GLOBAL_AGENT_LIBRARY,
        PIRSlotBehavior.REAL_QUERY,
    ),
    IntegrationCase(
        "LIBRARY_FALLBACK_MULTI_CANDIDATE",
        (7, 8),
        (),
        7,
        PrivateResolutionSource.GLOBAL_AGENT_LIBRARY,
        PIRSlotBehavior.REAL_QUERY,
    ),
)


def descriptor(agent_id: int, *, enterprise: bool) -> AgentDescriptorV7:
    placement = PlacementClass.CLOUD_LOCAL if enterprise else PlacementClass.EXTERNAL
    source = "enterprise" if enterprise else "global"
    route = f"private-{source}-agent-{agent_id}"
    return AgentDescriptorV7(
        agent_id=agent_id,
        capability_ids=(f"agent.service.{agent_id}",),
        publisher_key_id=f"publisher-{source}",
        agent_version=1,
        placement=placement,
        agent_service=AgentServiceRouteDescriptor(
            route_handle=route,
            effect_semantics=EffectSemantics.READ_ONLY,
            policy_id=f"policy-{source}-{agent_id}",
            placement=placement,
        ),
        allowed_tool_capabilities=(),
        trust_class=f"V13B_{source.upper()}_FIXTURE",
        catalog_epoch=20260829,
    ).validated()


def action_case(framework: str, item: IntegrationCase) -> V11ActionCase:
    marker = "oa" if framework.startswith("OpenAI") else "ms"
    operation_id = f"v13b-{marker}-{item.name.lower()}"[:32]
    return V11ActionCase(
        case_id=f"{operation_id}-case",
        framework=framework,
        action_family=CanonicalActionFamily.AGENT_SERVICE,
        logical_action_name="resolve_enterprise_agent",
        argument_schema=ArgumentSchema(
            "v13b-agent-task",
            (ArgumentField("task", "str"),),
        ),
        arguments={"task": "bounded enterprise task"},
        effect_semantics="READ_ONLY",
        scenario="SUCCESS",
        operation_id=operation_id,
        capability=f"agent.service.{item.selected_id}",
        agent_id=item.selected_id,
        agent_capability=f"agent.service.{item.selected_id}",
        agent_service_subtype=AgentServiceSubtype.DIRECT_AGENT_SERVICE,
    ).validate()


def build(
    framework: str, item: IntegrationCase
) -> tuple[
    V11ActionCase,
    TwoTierFrameworkGatewayComposition,
    DeterministicMockPSIBackend,
    MockPIRSlotBackend,
    ExistingGatewayControlChannelAdapter,
    io.StringIO,
]:
    records = [
        EnterpriseAgentRecord(
            canonical_agent_id=value,
            private_execution_handle=f"enterprise-cloud-deployment-{value}",
            descriptor=descriptor(value, enterprise=True),
            descriptor_version=1,
        )
        for value in item.enterprise_ids
    ]
    directory = EnterpriseAgentDirectory(records)
    psi = DeterministicMockPSIBackend(directory)
    counter = iter(range(500, 10_000))
    availability = FixedProfilePrivateAgentAvailabilityResolver(
        psi,
        default_psi_profile(),
        dummy_identifier_source=lambda: (1 << 63) + next(counter),
    )
    library = {
        value: descriptor(value, enterprise=False)
        for value in set(item.candidates)
    }
    pir = MockPIRSlotBackend(library)
    stream = io.StringIO()

    def receive(
        operation_id: str,
        _target: Any,
        _action: dict[str, object],
    ) -> ExistingGatewayResult:
        return ExistingGatewayResult(
            operation_id=operation_id,
            result="enterprise-task-complete",
            effect_count=0,
            outcome_semantics="READ_ONLY:SUCCESS",
        )

    gateway = ExistingGatewayControlChannelAdapter(stream, receive)
    resolver = TwoTierPrivateAgentResolver(availability, directory, pir, gateway)
    case = action_case(framework, item)
    composition = TwoTierFrameworkGatewayComposition(
        resolver,
        gateway,
        {case.operation_id: PlannerCandidateSet.from_sequence(item.candidates)},
    )
    return case, composition, psi, pir, gateway, stream


@pytest.mark.parametrize("framework", FRAMEWORKS)
@pytest.mark.parametrize("item", CASES, ids=lambda value: value.name)
def test_framework_two_tier_resolution_reaches_existing_gateway_once(
    framework: str, item: IntegrationCase
) -> None:
    case, composition, psi, pir, gateway, stream = build(framework, item)
    framework_result = run_online_framework_workflow(
        framework, "DYNAMIC_SEQUENCE", [case], composition
    )
    trajectory = framework_result["projection"]["trajectory"]
    assert len(trajectory) == 1
    assert trajectory[0]["operation_id"] == case.operation_id
    assert trajectory[0]["result"] == "enterprise-task-complete"
    assert trajectory[0]["outcome"] == "READ_ONLY:SUCCESS"
    assert composition.executed_operation_ids == [case.operation_id]
    assert len(psi.calls) == 1 and len(psi.calls[0]) == 8
    assert len(pir.calls) == 1
    assert len(gateway.submitted_private_targets) == 1
    target = gateway.submitted_private_targets[0]
    assert target.canonical_agent_id == item.selected_id
    assert target.source is item.source
    assert (
        target.descriptor.placement
        is (
            PlacementClass.CLOUD_LOCAL
            if item.source is PrivateResolutionSource.ENTERPRISE_DEPLOYED_AGENT
            else PlacementClass.EXTERNAL
        )
    )
    assert (
        (pir.calls[0][1] is None)
        if item.pir_behavior is PIRSlotBehavior.PADDING_QUERY
        else (pir.calls[0][1] == item.selected_id)
    )
    messages = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(messages) == 1
    assert messages[0]["type"] == "SUBMIT_RESOLVED_ACTION"
    assert messages[0]["action"]["route_handle"] == target.private_execution_handle
    assert gateway.direct_tee_to_agent_connections == 0


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_hit_and_fallback_public_structural_views_are_byte_equal(
    framework: str,
) -> None:
    local_item = CASES[0]
    fallback_item = CASES[2]
    local_case, local_composition, *_ = build(framework, local_item)
    fallback_case, fallback_composition, *_ = build(framework, fallback_item)
    local_outcome = local_composition(local_case, local_case.arguments)
    fallback_outcome = fallback_composition(fallback_case, fallback_case.arguments)
    local_public = local_outcome.evidence["public_structural_projection"]
    fallback_public = fallback_outcome.evidence["public_structural_projection"]
    assert json.dumps(local_public, sort_keys=True, separators=(",", ":")).encode() == (
        json.dumps(fallback_public, sort_keys=True, separators=(",", ":")).encode()
    )
    encoded = json.dumps(local_public, sort_keys=True)
    for forbidden in (
        "candidate_ids",
        "intersection",
        "enterprise_hit",
        "selected_agent_id",
        "pir_behavior",
        "descriptor",
        "route_handle",
        "source_class",
        "private_execution_handle",
        "operation_id",
    ):
        assert forbidden not in encoded


def test_receiver_only_psi_contract_is_explicit_and_mock_is_not_crypto() -> None:
    contract = ReceiverOnlyPSIContract().validated()
    assert PSI_VARIANT_REQUIRED == "RECEIVER_ONLY_PSI_OR_PRIVATE_SET_MEMBERSHIP"
    assert PSI_OUTPUT_RECIPIENT == "TRUSTED_RUNTIME_ONLY"
    assert ENTERPRISE_DIRECTORY_LEARNS_INTERSECTION is False
    assert contract.enterprise_directory_learns_candidate_set is False
    assert contract.enterprise_directory_learns_selected_agent is False
    assert contract.enterprise_directory_learns_branch_bit is False
    _case, _composition, psi, *_ = build("OpenAI Agents SDK", CASES[0])
    assert psi.cryptographic_status == "NOT_CRYPTOGRAPHICALLY_INSTANTIATED"


def test_execution_identity_audit_has_no_direct_connection() -> None:
    audit = execution_identity_audit()
    assert audit["direct_tee_to_enterprise_agent_connections"] == 0
    assert audit["composition_network_clients"] == 0
    assert audit["source_class_in_public_projection"] is False
    assert audit["private_route_in_public_projection"] is False
    assert audit["classification"] == "OUTSIDE_FROZEN_OBSERVER_AFTER_COMMON_GATEWAY"


def test_composition_layer_contains_no_direct_network_client() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "v13_private_resolution"
        / "e2e.py"
    ).read_text(encoding="utf-8")
    imported_roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(
        {"http", "socket", "subprocess", "urllib", "requests", "aiohttp"}
    )


def test_composition_public_constants_match_frozen_v4r8_evidence() -> None:
    profile = duplex_response_anchor_p10_profile()
    assert profile.total_rounds == GATEWAY_PUBLIC_CELL_COUNT == 521
    assert profile.pir_resolution_opportunities == 100
    assert profile.request_final_bytes == GATEWAY_REQUEST_BYTES == 1079
    assert profile.response_final_bytes == GATEWAY_RESPONSE_BYTES == 800
    communication = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "V12_V4R8_FINAL_UTILITY_SERVER_CLOSURE_EVIDENCE"
            / "final_communication_overhead.json"
        ).read_text(encoding="utf-8")
    )
    assert communication["registry_query_bytes"] == PIR_QUERY_BYTES == 2020
    assert communication["registry_answer_bytes"] == PIR_ANSWER_BYTES == 6592
