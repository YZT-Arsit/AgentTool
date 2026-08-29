from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from canonical_v9.runner import GO_RUNNER
from v10_1_executor import CaseSpec
from v10_1_executor.registry import eligible_adapter
from v10_1_executor.semantic import run_canonical_case, run_native_case
from v10_1_executor.structural import StructuralAction, StructuralArmSpec, run_structural_arm


ROOT = Path(__file__).resolve().parents[1]
OLD_MANIFESTS = (
    ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json",
    ROOT / "STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json",
)


def _hashes() -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in OLD_MANIFESTS}


def _case(framework: str, suffix: str, **changes: str) -> CaseSpec:
    adapter = (
        "OPENAI_GENERIC_FUNCTION_TOOL_V10_1"
        if framework == "OpenAI Agents SDK"
        else "MICROSOFT_GENERIC_FUNCTION_TOOL_V10_1"
    )
    values = {
        "case_id": f"NON-HOLDOUT-V9-DEV-{suffix}",
        "framework": framework,
        "adapter_id": adapter,
        "action_family": "tool",
        "prompt": "Execute the deterministic non-holdout local action.",
        "protected_argument": f"argument-{suffix}",
        "operation_id": f"v101dev{suffix}",
        "source_path": "SYNTHETIC_NON_HOLDOUT_FIXTURE",
    }
    values.update(changes)
    return CaseSpec(**values)


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
def test_native_framework_executor_uses_real_action_machinery(framework: str) -> None:
    record = run_native_case(_case(framework, "native" + ("o" if framework.startswith("OpenAI") else "m")))
    evidence = record.execution_evidence
    assert evidence["framework_instantiated"]
    assert evidence["action_registered"]
    assert evidence["native_action_boundary_reached"]
    assert evidence["provider_request_observed"]
    assert evidence["framework_received_result"]


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
@pytest.mark.parametrize(
    ("suffix", "changes"),
    [
        ("read", {}),
        ("idem", {"capability": "tool.idem", "effect_semantics": "IDEMPOTENT_EFFECT"}),
        ("nonidem", {"capability": "tool.nonidem", "effect_semantics": "NON_IDEMPOTENT_EFFECT"}),
        ("error", {"scenario": "ERROR"}),
        ("timeout", {"scenario": "BOUNDED_TIMEOUT"}),
    ],
)
def test_native_and_canonical_records_are_independently_executed_and_equal(
    tmp_path: Path, framework: str, suffix: str, changes: dict[str, str]
) -> None:
    assert GO_RUNNER.is_file(), "accepted canonical-v9-runner binary is required; no Python substitute is permitted"
    marker = "o" if framework.startswith("OpenAI") else "m"
    case = _case(framework, marker + suffix, **changes)
    if suffix == "read":
        case = CaseSpec(**{**case.__dict__, "logical_action_name": "lookup_weather", "argument_name": "city"})
    before = _hashes()
    native = run_native_case(case)
    canonical = run_canonical_case(case, tmp_path / f"canonical-{marker}-{suffix}")
    assert native.projection() == canonical.projection()
    assert native.execution_evidence["execution_path"] != canonical.execution_evidence["execution_path"]
    bridge = canonical.execution_evidence["canonical_bridge"]
    assert bridge["official_simplepir_recovery"]
    assert bridge["authenticated_agent_descriptor_v7"]
    assert bridge["delivery_ledger"]["missing"] == []
    assert bridge["dummy_provider_operations"] == 0
    assert _hashes() == before


def test_adapter_registry_does_not_promote_unsupported_families() -> None:
    assert eligible_adapter("OpenAI Agents SDK", "tool") is not None
    assert eligible_adapter("Microsoft Agent Framework", "tool") is not None
    assert eligible_adapter("OpenAI Agents SDK", "handoff") is None
    assert eligible_adapter("OpenAI Agents SDK", "agents_as_tools") is None


def test_structural_executor_on_non_holdout_v9_1_development_pair(tmp_path: Path) -> None:
    assert GO_RUNNER.is_file(), "accepted canonical-v9-runner binary is required; no projection-only substitute is permitted"
    before = _hashes()
    left = StructuralArmSpec(
        "NON-HOLDOUT-V9_1-DIFFERENT-TOOL-A",
        10,
        "agent.tools",
        (StructuralAction("v101structa", "tool.read", "TOOL", "development-a"),),
    )
    right = StructuralArmSpec(
        "NON-HOLDOUT-V9_1-DIFFERENT-TOOL-B",
        10,
        "agent.tools",
        (StructuralAction("v101structb", "tool.idem", "TOOL", "development-b"),),
    )
    a = run_structural_arm(left, output=tmp_path / "left")
    b = run_structural_arm(right, output=tmp_path / "right")
    assert a.functional and b.functional
    assert a.strict_structural_projection == b.strict_structural_projection
    assert a.strict_size_projection == b.strict_size_projection
    assert _hashes() == before
