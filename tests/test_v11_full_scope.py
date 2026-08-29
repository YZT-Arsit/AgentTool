from __future__ import annotations

from dataclasses import replace

import pytest

from v11_full_scope.canonical import (
    canonical_external_outcome,
    canonical_internal_outcome,
    canonical_multi_action,
    native_local_outcome,
    public_projections,
)
from v11_full_scope.fixtures import SCHEMAS_AND_VALUES, agent_case, tool_case, with_readiness
from v11_full_scope.frameworks import canonical_implementation, native_implementation, run_framework_case
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily, V11ActionCase
from v11_full_scope.structural import run_development_pair, validate_structural_action


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
@pytest.mark.parametrize("schema_index", range(len(SCHEMAS_AND_VALUES)))
def test_generic_structured_tools_native_and_canonical(framework, schema_index, tmp_path):
    case = tool_case(f"structured-{framework[0]}-{schema_index}", framework, schema_index)
    native = run_framework_case(case, native_implementation)
    canonical = run_framework_case(case, canonical_implementation(tmp_path / "canonical"))
    assert native.projection() == canonical.projection()
    assert canonical.final_framework_visible_result_state["action_result_received"]
    evidence = canonical.runtime_evidence["action_implementation_evidence"]
    assert evidence["official_simplepir"]
    assert evidence["rfc9292_rfc9458"]
    assert evidence["dummy_provider_operations"] == 0


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
def test_real_agent_as_tool_native_and_canonical(framework, tmp_path):
    case = agent_case(f"agent-tool-{framework[0]}", framework, AgentServiceSubtype.AGENT_AS_TOOL)
    native = run_framework_case(case, native_implementation)
    canonical = run_framework_case(case, canonical_implementation(tmp_path / "canonical"))
    assert native.projection() == canonical.projection()
    assert "as_tool" in canonical.runtime_evidence["actual_framework_api"]
    assert canonical.runtime_evidence["remote_child_executed_directly"] is False
    assert canonical.runtime_evidence["action_implementation_evidence"]["private_subtype"] == "AGENT_AS_TOOL"


def test_real_openai_handoff_native_and_canonical(tmp_path):
    case = agent_case("openai-handoff", "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF)
    native = run_framework_case(case, native_implementation)
    canonical = run_framework_case(case, canonical_implementation(tmp_path / "canonical"))
    assert native.projection() == canonical.projection()
    assert canonical.runtime_evidence["actual_framework_api"] == "agents.handoff"
    assert canonical.runtime_evidence["handoff_boundary_reached"]
    assert canonical.runtime_evidence["last_agent_is_target"]
    assert canonical.runtime_evidence["remote_target_executed_directly"] is False


def test_microsoft_handoff_is_absent_not_invented():
    case = agent_case("microsoft-handoff", "Microsoft Agent Framework", AgentServiceSubtype.HANDOFF)
    with pytest.raises(NotImplementedError, match="FRAMEWORK_NATIVE_MECHANISM_ABSENT"):
        run_framework_case(case, native_implementation)


@pytest.mark.parametrize(
    ("family", "effect", "scenario"),
    [
        (CanonicalActionFamily.TOOL, "READ_ONLY", "SUCCESS"),
        (CanonicalActionFamily.TOOL, "IDEMPOTENT_EFFECT", "SUCCESS"),
        (CanonicalActionFamily.TOOL, "NON_IDEMPOTENT_EFFECT", "SUCCESS"),
        (CanonicalActionFamily.TOOL, "READ_ONLY", "ERROR"),
        (CanonicalActionFamily.TOOL, "READ_ONLY", "BOUNDED_TIMEOUT"),
        (CanonicalActionFamily.TOOL, "NON_IDEMPOTENT_EFFECT", "BOUNDED_TIMEOUT"),
    ],
)
def test_effect_and_outcome_matrix(family, effect, scenario, tmp_path):
    case = tool_case(f"effect-{effect[:4]}-{scenario[:4]}", "OpenAI Agents SDK", 0, effect, scenario)
    native = run_framework_case(case, native_implementation)
    canonical = run_framework_case(case, canonical_implementation(tmp_path / "canonical"))
    assert native.projection() == canonical.projection()
    if effect == "NON_IDEMPOTENT_EFFECT" and scenario == "BOUNDED_TIMEOUT":
        assert canonical.operation_outcome_semantics.endswith("EFFECT_OUTCOME_UNKNOWN")


def test_external_http_and_direct_agent_service(tmp_path):
    tool = tool_case("external-http", "OpenAI Agents SDK")
    external = replace(
        tool,
        action_family=CanonicalActionFamily.EXTERNAL_HTTP,
        capability="external.local",
        logical_action_name="external_http",
    )
    external_result = canonical_external_outcome(external, tmp_path / "external")
    direct = agent_case("direct-service", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    direct_result = canonical_external_outcome(direct, tmp_path / "direct")
    assert external_result.outcome_semantics == "READ_ONLY:SUCCESS"
    assert direct_result.outcome_semantics == "READ_ONLY:SUCCESS"
    assert external_result.evidence["dummy_provider_operations"] == 0
    assert direct_result.evidence["dummy_provider_operations"] == 0


def test_internal_trusted_path_and_external_strict_projection(tmp_path):
    internal = agent_case(
        "internal-strict",
        "FRAMEWORK_NEUTRAL",
        AgentServiceSubtype.DIRECT_AGENT_SERVICE,
        placement="TRUSTED_MODULE_LOCAL",
    )
    external = agent_case("external-strict", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    internal_result = canonical_internal_outcome(internal, tmp_path / "internal")
    external_result = canonical_external_outcome(external, tmp_path / "external")
    assert internal_result.evidence["hardware_tee"] is False
    assert internal_result.evidence["cover_trace"]["provider_invocations"] == 0
    assert internal_result.evidence["dummy_provider_operations"] == 0
    assert public_projections(internal_result) == public_projections(external_result)
    assert internal_result.evidence["result_multiplexer"]["replay_suppressed"]


def test_structural_generator_binds_effect_semantics():
    validate_structural_action(1, "agent.a", {"action_kind": "TOOL", "capability": "tool.a", "effect_semantics": "READ_ONLY"})
    with pytest.raises(ValueError, match="effect semantics mismatch"):
        validate_structural_action(2, "agent.b", {"action_kind": "TOOL", "capability": "tool.b", "effect_semantics": "READ_ONLY"})
    validate_structural_action(2, "agent.b", {"action_kind": "TOOL", "capability": "tool.b", "effect_semantics": "IDEMPOTENT_EFFECT"})


def test_controlled_private_completion_behavior_keeps_structure_and_size(tmp_path):
    base = tool_case("readiness-a", "FRAMEWORK_NEUTRAL")
    early = with_readiness(base, "EARLY_READY")
    late = with_readiness(replace(base, case_id="readiness-b", operation_id="opreadinessb"), "LATE_READY_WITHIN_BOUND")
    result = run_development_pair(early, late, tmp_path / "pair")
    assert result.functional
    assert result.structural_equal
    assert result.size_equal
    assert early.continuation != late.continuation


@pytest.mark.parametrize("count", [1, 10, 50])
def test_tool_multi_action_capacity(count, tmp_path):
    cases = [
        replace(tool_case(f"multi-{count}-{index}", "FRAMEWORK_NEUTRAL"), operation_id=f"v11multi{count:02d}{index:03d}")
        for index in range(count)
    ]
    result = canonical_multi_action(cases, tmp_path / f"multi-{count}")
    assert result["functional"]
    assert result["admitted"] == count
    assert result["delivered"] == count
    assert result["dummy_provider_operations"] == 0
    assert result["profile_overflow_events"] == 0


def test_agent_service_private_subtype_fits_existing_bucket(tmp_path):
    case = agent_case("max-envelope", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.AGENT_AS_TOOL)
    case = replace(
        case,
        continuation={"context": "x" * 128},
        arguments={"task": "y" * 128},
    )
    result = canonical_external_outcome(case, tmp_path / "max-envelope")
    assert result.evidence["raw_trace"]["request_final_bytes"] == 1079
    assert len(result.evidence["raw_trace"]["public_relay_events"]) == 111


def test_oversize_private_envelope_is_rejected_without_profile_resize(tmp_path):
    case = agent_case("oversize-envelope", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.AGENT_AS_TOOL)
    case = replace(
        case,
        continuation={"context": "x" * 256},
        arguments={"task": "y" * 256},
    )
    with pytest.raises(ValueError, match="frozen public BHTTP bucket is not resized"):
        canonical_external_outcome(case, tmp_path / "oversize-envelope")
