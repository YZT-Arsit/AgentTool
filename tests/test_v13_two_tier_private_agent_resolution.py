from __future__ import annotations

import json

import pytest

from action_privacy_v8 import (
    AgentDescriptorV7,
    AgentServiceRouteDescriptor,
    EffectSemantics,
    PlacementClass,
)
from v13_private_resolution import (
    DeterministicMockPSIBackend,
    EnterpriseAgentDirectory,
    EnterpriseAgentRecord,
    ExistingSimplePIRSlotAdapter,
    FailingMockPSIBackend,
    FixedProfilePrivateAgentAvailabilityResolver,
    MockPIRSlotBackend,
    PIRSlotBehavior,
    PSI_CRYPTO_BACKEND_STATUS,
    PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE,
    PrivateResolutionSource,
    RecordingTrustedGateway,
    TwoTierPrivateAgentResolver,
    TwoTierResolutionError,
    default_psi_profile,
)


def descriptor(agent_id: int, placement: PlacementClass) -> AgentDescriptorV7:
    return AgentDescriptorV7(
        agent_id=agent_id,
        capability_ids=(f"agent.service.{agent_id}",),
        publisher_key_id="publisher-enterprise-test",
        agent_version=1,
        placement=placement,
        agent_service=AgentServiceRouteDescriptor(
            route_handle=f"route-agent-{agent_id}",
            effect_semantics=EffectSemantics.READ_ONLY,
            policy_id=f"policy-agent-{agent_id}",
            placement=placement,
        ),
        allowed_tool_capabilities=(),
        trust_class="V13_FUNCTIONAL_FIXTURE",
        catalog_epoch=20260829,
    ).validated()


def record(agent_id: int) -> EnterpriseAgentRecord:
    return EnterpriseAgentRecord(
        canonical_agent_id=agent_id,
        private_execution_handle=f"enterprise-cloud-handle-{agent_id}",
        descriptor=descriptor(agent_id, PlacementClass.CLOUD_LOCAL),
        descriptor_version=1,
    ).validated()


def build(
    enterprise_ids: tuple[int, ...],
    *,
    psi_backend_factory=DeterministicMockPSIBackend,
) -> tuple[
    TwoTierPrivateAgentResolver,
    DeterministicMockPSIBackend | FailingMockPSIBackend,
    MockPIRSlotBackend,
    RecordingTrustedGateway,
]:
    directory = EnterpriseAgentDirectory(record(value) for value in enterprise_ids)
    psi = psi_backend_factory(directory)
    counter = iter(range(100, 10_000))
    availability = FixedProfilePrivateAgentAvailabilityResolver(
        psi,
        default_psi_profile(),
        dummy_identifier_source=lambda: (1 << 63) + next(counter),
    )
    library = {
        value: descriptor(value, PlacementClass.EXTERNAL)
        for value in range(1, 20)
    }
    pir = MockPIRSlotBackend(library)
    gateway = RecordingTrustedGateway()
    return (
        TwoTierPrivateAgentResolver(availability, directory, pir, gateway),
        psi,
        pir,
        gateway,
    )


def test_singleton_local_hit_uses_enterprise_agent_and_padding_pir() -> None:
    resolver, psi, pir, gateway = build((7,))
    outcome = resolver.resolve_and_handoff("op-local", [7])
    assert outcome.private.enterprise_hit
    assert outcome.private.source is PrivateResolutionSource.ENTERPRISE_DEPLOYED_AGENT
    assert outcome.private.selected_agent_id == 7
    assert outcome.private.pir_behavior is PIRSlotBehavior.PADDING_QUERY
    assert pir.calls == [("op-local", None)]
    assert len(psi.calls) == 1 and len(psi.calls[0]) == 8
    assert gateway.destinations[0].private_execution_handle == "enterprise-cloud-handle-7"


def test_singleton_library_fallback_uses_real_pir_row() -> None:
    resolver, psi, pir, gateway = build(())
    outcome = resolver.resolve_and_handoff("op-fallback", [7])
    assert not outcome.private.enterprise_hit
    assert outcome.private.source is PrivateResolutionSource.GLOBAL_AGENT_LIBRARY
    assert outcome.private.pir_behavior is PIRSlotBehavior.REAL_QUERY
    assert pir.calls == [("op-fallback", 7)]
    assert len(psi.calls) == 1
    assert gateway.destinations[0].descriptor.placement is PlacementClass.EXTERNAL


def test_multi_candidate_one_hit_selects_the_only_enterprise_match() -> None:
    resolver, _psi, pir, gateway = build((7,))
    outcome = resolver.resolve_and_handoff("op-one-hit", [6, 7, 8])
    assert outcome.private.matched_ids == (7,)
    assert outcome.private.selected_agent_id == 7
    assert pir.calls == [("op-one-hit", None)]
    assert gateway.destinations[0].canonical_agent_id == 7


def test_multi_candidate_multiple_hits_use_frozen_planner_order() -> None:
    resolver, _psi, pir, gateway = build((7, 8))
    outcome = resolver.resolve_and_handoff("op-multi-hit", [8, 7, 6])
    assert outcome.private.matched_ids == (8, 7)
    assert outcome.private.selected_agent_id == 8
    assert resolver.selector_policy == "FIRST_PLANNER_ORDER_MATCH_ELSE_FIRST_CANDIDATE"
    assert pir.calls == [("op-multi-hit", None)]
    assert gateway.destinations[0].canonical_agent_id == 8


def test_no_hit_uses_first_planner_candidate_for_library_fallback() -> None:
    resolver, _psi, pir, _gateway = build(())
    outcome = resolver.resolve_and_handoff("op-no-hit", [9, 10])
    assert outcome.private.matched_ids == ()
    assert outcome.private.selected_agent_id == 9
    assert pir.calls == [("op-no-hit", 9)]


def test_psi_error_fails_closed_after_fixed_padding_pir_slot() -> None:
    directory = EnterpriseAgentDirectory([record(7)])
    psi = FailingMockPSIBackend()
    availability = FixedProfilePrivateAgentAvailabilityResolver(
        psi,
        default_psi_profile(),
        dummy_identifier_source=iter(range(1 << 63, (1 << 63) + 20)).__next__,
    )
    pir = MockPIRSlotBackend({7: descriptor(7, PlacementClass.EXTERNAL)})
    gateway = RecordingTrustedGateway()
    resolver = TwoTierPrivateAgentResolver(availability, directory, pir, gateway)
    with pytest.raises(TwoTierResolutionError) as failure:
        resolver.resolve_and_handoff("op-psi-error", [7])
    assert psi.calls == 1
    assert pir.calls == [("op-psi-error", None)]
    assert gateway.destinations == []
    assert failure.value.public.psi_slot_count == 1
    assert failure.value.public.pir_slot_count == 1
    assert failure.value.public.gateway_public_path_count == 1
    successful, _psi2, _pir2, _gateway2 = build((7,))
    assert failure.value.public.public_view() == successful.resolve_and_handoff(
        "op-success-shape", [7]
    ).public_view()


def test_enterprise_and_global_resolution_use_same_gateway_abstraction() -> None:
    local, _psi1, _pir1, local_gateway = build((7,))
    global_, _psi2, _pir2, global_gateway = build(())
    local.resolve_and_handoff("op-local-gateway", [7])
    global_.resolve_and_handoff("op-global-gateway", [7])
    assert len(local_gateway.destinations) == len(global_gateway.destinations) == 1
    assert type(local_gateway) is type(global_gateway) is RecordingTrustedGateway


def test_public_branch_equivalence_hides_hit_and_pir_behavior() -> None:
    local, _psi1, _pir1, _gateway1 = build((7,))
    global_, _psi2, _pir2, _gateway2 = build(())
    local_view = local.resolve_and_handoff("op-local-public", [7]).public_view()
    global_view = global_.resolve_and_handoff("op-global-public", [7]).public_view()
    assert local_view == global_view
    encoded = json.dumps(local_view, sort_keys=True)
    for forbidden in (
        "candidate_ids",
        "matched_ids",
        "enterprise_hit",
        "selected_agent_id",
        "pir_behavior",
        "private_execution_handle",
    ):
        assert forbidden not in encoded
    assert local_view["psi_slot_count"] == local_view["pir_slot_count"] == 1
    assert local_view["gateway_public_cell_count"] == 521
    assert local_view["registry_public_query_count"] == 100


@pytest.mark.parametrize("candidate_count", range(1, 9))
def test_candidate_sizes_one_through_k_have_identical_public_batch_size(
    candidate_count: int,
) -> None:
    resolver, psi, _pir, _gateway = build(())
    candidates = list(range(1, candidate_count + 1))
    outcome = resolver.resolve_and_handoff(f"op-k-{candidate_count}", candidates)
    assert len(psi.calls[0]) == 8
    assert outcome.public.profile.candidate_batch_k == 8
    assert outcome.public.public_view()["request_message_size_class"] == "PSI-REQUEST-K8-E1024"


def test_enterprise_inventory_is_padded_to_public_bound() -> None:
    resolver, psi, _pir, _gateway = build((7, 8))
    resolver.resolve_and_handoff("op-e-padding", [7])
    assert psi.server_inventory_sizes == [1024]
    assert resolver.availability.profile.enterprise_cardinality_policy.value == "PADDED"
    assert resolver.availability.profile.enterprise_cardinality_bound == 1024


def test_existing_simplepir_adapter_selects_padding_and_real_rows() -> None:
    class FakeOnlineSimplePIR:
        cover_dummy_index = 999

        def __init__(self) -> None:
            self.calls: list[tuple[str, int]] = []

        def query(self, operation_id: str, index: int) -> AgentDescriptorV7:
            self.calls.append((operation_id, index))
            return descriptor(index, PlacementClass.EXTERNAL)

        def resolve_descriptor(self, operation_id: str, index: int) -> AgentDescriptorV7:
            self.calls.append((operation_id, index))
            return descriptor(index, PlacementClass.EXTERNAL)

    online = FakeOnlineSimplePIR()
    adapter = ExistingSimplePIRSlotAdapter(online)
    padding = adapter.execute_slot("op-pad", None)
    real = adapter.execute_slot("op-real", 7)
    assert padding.behavior is PIRSlotBehavior.PADDING_QUERY
    assert padding.descriptor is None
    assert real.behavior is PIRSlotBehavior.REAL_QUERY
    assert real.descriptor is not None and real.descriptor.agent_id == 7
    assert online.calls == [("op-pad:library-padding", 999), ("op-real", 7)]


def test_v4r8_gateway_and_registry_public_counts_are_not_redefined() -> None:
    resolver, _psi, _pir, _gateway = build((7,))
    public = resolver.resolve_and_handoff("op-profile", [7]).public_view()
    assert public["gateway_public_cell_count"] == 521
    assert public["registry_public_query_count"] == 100


def test_mock_backend_never_claims_cryptographic_psi() -> None:
    _resolver, psi, _pir, _gateway = build((7,))
    assert psi.cryptographic_status == "NOT_CRYPTOGRAPHICALLY_INSTANTIATED"
    assert PSI_CRYPTO_BACKEND_STATUS == "NOT_CRYPTOGRAPHICALLY_INSTANTIATED"


def test_same_trusted_domain_deployment_status_is_explicit() -> None:
    assert (
        PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE
        == "PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE"
    )
