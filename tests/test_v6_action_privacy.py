from __future__ import annotations

import importlib
import os
import sys

import pytest

from action_privacy_v6.adapters import (DeterministicLocalProvider,
                                        FrameworkActionAdapter, NativeAction,
                                        execute_mediated, execute_native)
from action_privacy_v6.descriptor import (DESCRIPTOR_BYTES, AgentDescriptorV6,
                                          DescriptorCodec, PlacementClass)
from action_privacy_v6.models import (ACTION_CELL_BYTES, ActionKind,
                                      ProtectedActionIntent)
from action_privacy_v6.resolution import ResolutionMode, V6Resolver
from action_privacy_v6.trusted_module import LocalTrustedBackend
from action_privacy_v6.bootstrap import bootstrap_local_v6


def descriptor(agent_id: int = 7, capability: str = "weather") -> AgentDescriptorV6:
    return AgentDescriptorV6(agent_id, (capability,), "publisher-test", 3,
                             PlacementClass.EXTERNAL, "route-opaque-7", "openai-agent-sdk",
                             ("tool.weather",), "SIGNED_ENTERPRISE", 11)


def backend(capability: str = "weather") -> tuple[LocalTrustedBackend, DescriptorCodec]:
    key = bytes(range(32))
    return LocalTrustedBackend({capability: 7}, key, bytes(reversed(range(32))), 11), DescriptorCodec(key, 11)


def test_descriptor_is_fixed_authenticated_and_binds_agent_epoch():
    trusted, codec = backend()
    row = codec.encode(descriptor())
    assert len(row) == DESCRIPTOR_BYTES
    assert trusted.recover_descriptor(row, 7) == descriptor()
    corrupt = bytearray(row)
    corrupt[-1] ^= 1
    with pytest.raises(Exception):
        trusted.recover_descriptor(bytes(corrupt), 7)
    with pytest.raises(PermissionError):
        trusted.recover_descriptor(row, 8)
    with pytest.raises(Exception):
        DescriptorCodec(bytes(range(32)), 12).decode(row, 7)


def test_action_cell_is_fixed_and_keeps_route_private_from_public_bytes():
    trusted, _ = backend()
    intent = ProtectedActionIntent("weather", b'{"city":"synthetic"}', "s1", "op1", ActionKind.TOOL)
    cell = trusted.make_action_cell(intent, descriptor(), public_profile="STRICT-STANDARD", public_slot=1)
    assert len(cell) == ACTION_CELL_BYTES
    assert b"route-opaque-7" not in cell and b"weather" not in cell
    opened = trusted.open_action_cell(cell, public_profile="STRICT-STANDARD", public_slot=1)
    assert opened.route_handle == "route-opaque-7"
    assert opened.operation_id == "op1"
    with pytest.raises(Exception):
        trusted.open_action_cell(cell, public_profile="STRICT-STANDARD", public_slot=2)


def test_unified_and_hierarchical_resolution_declare_different_leakage():
    trusted, codec = backend()
    row = codec.encode(descriptor())
    resolver = V6Resolver(trusted, lambda _: row, internal_ids=frozenset({7}))
    intent = ProtectedActionIntent("weather", b"{}", "s", "op", ActionKind.TOOL)
    unified = resolver.resolve(intent, ResolutionMode.UNIFIED_PRIVATE_REGISTRY)
    hierarchical = resolver.resolve(intent, ResolutionMode.HIERARCHICAL_PRIVATE_RESOLUTION)
    assert unified.public_route_class == "OPAQUE" and unified.route_leakage == "NONE"
    assert hierarchical.public_route_class == "INTERNAL"
    assert hierarchical.route_leakage == "INTERNAL_EXTERNAL_ROUTE_CLASS"


def test_strict_cache_hit_still_requires_public_pir_slot():
    trusted, codec = backend()
    trusted.recover_descriptor(codec.encode(descriptor()), 7)
    strict = trusted.cache_decision(7, strict=True)
    efficient = trusted.cache_decision(7, strict=False)
    assert strict.descriptor is not None and strict.public_pir_required and strict.query_kind == "DUMMY_ROW"
    assert efficient.descriptor is not None and not efficient.public_pir_required


def test_framework_action_adapter_preserves_projection():
    action = NativeAction("OpenAI Agents SDK", "official/example.py", "weather", ActionKind.TOOL,
                          b"synthetic", "op-1")
    native_provider = DeterministicLocalProvider()
    mediated_provider = DeterministicLocalProvider()
    native = execute_native(action, native_provider, effectful=True)
    adapter = FrameworkActionAdapter("OpenAI Agents SDK")
    mediated = execute_mediated(
        action, adapter,
        lambda intent: mediated_provider.invoke(intent.capability, intent.protected_arguments,
                                                 intent.operation_id, effectful=True),
        session_id="s",
    )
    assert native == mediated


def test_canonical_v6_import_has_no_control_ir_dependency():
    for name in list(sys.modules):
        if name.startswith("action_privacy_v6") or name.startswith("agent_control_virtualization"):
            sys.modules.pop(name, None)
    importlib.import_module("action_privacy_v6")
    assert not any(name.startswith("agent_control_virtualization") for name in sys.modules)


def test_local_backend_labels_hardware_boundaries_honestly():
    trusted, _ = backend()
    assert trusted.hardware_tee_attestation == "NOT_TESTED"
    assert trusted.hardware_memory_confidentiality == "NOT_TESTED"
    assert trusted.rollback_protection == "OPEN"


def test_v6_local_bootstrap_derives_ephemeral_domain_keys_without_hardware_claim():
    keys = bootstrap_local_v6("ab" * 32)
    assert len(keys.descriptor_key) == len(keys.gateway_key) == 32
    assert keys.descriptor_key != keys.gateway_key
    assert keys.hardware_attestation == "NOT_TESTED"
