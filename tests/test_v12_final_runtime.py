from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from v11_full_scope.fixtures import agent_case, tool_case
from v11_full_scope.models import AgentServiceSubtype
from v11_online.session import OnlineSimplePIRResolver
from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    TrajectorySpec,
    run_canonical_online_trajectory_case,
    run_canonical_semantic_case,
    run_native_semantic_case,
    run_native_trajectory_case,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_4-runner"
PREBUILT_PIR_SHA256 = "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b"
PERMIT = ExecutionPermit("V11A_DEVELOPMENT_REGRESSION", True)


def _tool(case_id: str, framework: str, effect: str, scenario: str):
    capability = {
        "READ_ONLY": "tool.read",
        "IDEMPOTENT_EFFECT": "tool.idem",
        "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
    }[effect]
    return replace(
        tool_case(case_id, framework, effect_semantics=effect, scenario=scenario),
        capability=capability,
    )


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
@pytest.mark.parametrize(
    ("label", "effect", "scenario"),
    [
        ("read-success", "READ_ONLY", "SUCCESS"),
        ("idem-success", "IDEMPOTENT_EFFECT", "SUCCESS"),
        ("nonidem-success", "NON_IDEMPOTENT_EFFECT", "SUCCESS"),
        ("read-error", "READ_ONLY", "ERROR"),
        ("read-timeout", "READ_ONLY", "BOUNDED_TIMEOUT"),
    ],
)
def test_actual_v12_online_tool_semantics(
    tmp_path: Path, framework: str, label: str, effect: str, scenario: str
) -> None:
    marker = "openai" if framework.startswith("OpenAI") else "microsoft"
    case = _tool(f"DEV-V12-FINAL-{marker}-{label}", framework, effect, scenario)
    native = run_native_semantic_case(case, PERMIT)
    canonical = run_canonical_semantic_case(
        case, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert native.projection() == canonical.projection()
    evidence = canonical.runtime_evidence["action_implementation_evidence"]
    assert evidence["official_simplepir"]
    assert evidence["dynamic_agent_resolution"]
    assert evidence["one_online_session"]


@pytest.mark.parametrize("framework", ["OpenAI Agents SDK", "Microsoft Agent Framework"])
def test_actual_v12_online_agent_as_tool(tmp_path: Path, framework: str) -> None:
    marker = "openai" if framework.startswith("OpenAI") else "microsoft"
    case = agent_case(
        f"DEV-V12-FINAL-{marker}-agent-as-tool",
        framework,
        AgentServiceSubtype.AGENT_AS_TOOL,
    )
    native = run_native_semantic_case(case, PERMIT)
    canonical = run_canonical_semantic_case(
        case, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert native.projection() == canonical.projection()


def test_actual_v12_online_openai_handoff(tmp_path: Path) -> None:
    case = agent_case(
        "DEV-V12-FINAL-openai-handoff",
        "OpenAI Agents SDK",
        AgentServiceSubtype.HANDOFF,
    )
    native = run_native_semantic_case(case, PERMIT)
    canonical = run_canonical_semantic_case(
        case, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert native.projection() == canonical.projection()


def test_actual_v12_online_agent_service_subtype(tmp_path: Path) -> None:
    case = agent_case(
        "DEV-V12-FINAL-openai-direct-service",
        "OpenAI Agents SDK",
        AgentServiceSubtype.DIRECT_AGENT_SERVICE,
    )
    native = run_native_semantic_case(case, PERMIT)
    canonical = run_canonical_semantic_case(
        case, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert native.projection() == canonical.projection()
    assert canonical.agent_service_subtype == "DIRECT_AGENT_SERVICE"


def test_actual_v12_online_multi_action_causal(tmp_path: Path) -> None:
    actions = (
        _tool("DEV-V12-FINAL-causal-1", "OpenAI Agents SDK", "READ_ONLY", "SUCCESS"),
        _tool("DEV-V12-FINAL-causal-2", "OpenAI Agents SDK", "IDEMPOTENT_EFFECT", "SUCCESS"),
    )
    spec = TrajectorySpec(
        "DEV-V12-FINAL-causal",
        "OpenAI Agents SDK",
        "DYNAMIC_SEQUENCE",
        actions,
    )
    native = run_native_trajectory_case(spec, PERMIT)
    canonical = run_canonical_online_trajectory_case(
        spec, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert native["projection"] == canonical["semantic"]["projection"]
    assert canonical["causal_proof"]["passed"]
    assert canonical["causal_proof"]["startup_action_count"] == 0


@pytest.mark.skipif(os.name != "posix", reason="final selected runtime platform is Linux")
def test_actual_v12_prebuilt_pir_and_action_without_go_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = ROOT / "pir_integration" / "simplepir_bridge" / "acv-simplepir-online"
    assert binary.is_file()
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == PREBUILT_PIR_SHA256

    monkeypatch.setenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    assert shutil.which("go") is None

    with OnlineSimplePIRResolver(tmp_path / "direct-pir", record_count=64) as resolver:
        assert resolver.prebuilt_bridge_used
        recovered = resolver.query("DEV-V12-FINAL-no-go-query", 10)
        assert recovered.agent_id == 10

    case = _tool(
        "DEV-V12-FINAL-no-go-action",
        "OpenAI Agents SDK",
        "READ_ONLY",
        "SUCCESS",
    )
    canonical = run_canonical_semantic_case(
        case, tmp_path / "canonical", PERMIT, runner_binary=RUNNER
    )
    assert canonical.operation_outcome_semantics == "READ_ONLY:SUCCESS"
    summary = tmp_path / "canonical" / "pir" / "online_query_summary.json"
    assert '"prebuilt_bridge_binary": true' in summary.read_text(encoding="utf-8")

