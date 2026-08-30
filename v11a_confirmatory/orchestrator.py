from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from canonical_v9.runner import GO_RUNNER
from v11_4.profile import selected_profile
from v11_full_scope.frameworks import native_implementation, run_framework_case
from v11_full_scope.models import (
    AgentServiceSubtype,
    ArgumentField,
    ArgumentSchema,
    CanonicalActionFamily,
    V11ActionCase,
)
from v11_full_scope.structural import canonical_effect_semantics
from v11_online.frameworks import run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession

from .projection import size_projection, structural_prefix, structural_projection


PROFILE_ID = "V11_4-STRICT-ONLINE-H50-H3000-P10"
DECISION_CLASSES = {
    "PASS",
    "SEMANTIC_MISMATCH",
    "NATIVE_REFERENCE_FAIL",
    "CANONICAL_FUNCTIONAL_FAIL",
    "PROFILE_ADMISSION_CLOSED",
    "INFRASTRUCTURE_SCHEDULE_FAILURE",
    "TRANSPORT_FAILURE",
    "HARNESS_INTEGRITY_FAILURE",
}


@dataclass(frozen=True)
class ExecutionPermit:
    phase: str
    approved: bool
    capability_preflight_passed: bool = False

    def require(self, cases: Iterable[V11ActionCase]) -> None:
        values = list(cases)
        if not self.approved:
            raise PermissionError("execution permit is not approved")
        if self.phase == "V11A_DEVELOPMENT_REGRESSION":
            if any(not case.case_id.startswith("DEV-") for case in values):
                raise PermissionError("development permit cannot execute non-development case")
            return
        if self.phase == "V12":
            if not self.capability_preflight_passed:
                raise PermissionError("V12 capability preflight has not passed")
            return
        if self.phase != "V11B":
            raise PermissionError("selected execution requires an explicit frozen campaign permit")


@dataclass(frozen=True)
class TrajectorySpec:
    trajectory_id: str
    framework: str
    workflow: str
    actions: tuple[V11ActionCase, ...]
    pir_delay_ms: int = 0
    decision_delay_ms: int = 0


def _schema(value: dict[str, Any]) -> ArgumentSchema:
    fields = tuple(ArgumentField(str(item["name"]), str(item["primitive_type"])) for item in value["fields"])
    return ArgumentSchema(str(value["schema_id"]), fields).validate()


def _expected_effect(case: V11ActionCase) -> str:
    if case.placement == "TRUSTED_MODULE_LOCAL":
        if case.action_family is not CanonicalActionFamily.AGENT_SERVICE or case.agent_id != 20:
            raise ValueError("only the frozen internal Agent route may use TRUSTED_MODULE_LOCAL")
        return "READ_ONLY"
    return canonical_effect_semantics(
        case.agent_id,
        case.agent_capability,
        case.action_family.value,
        case.capability,
    )


def load_action(value: dict[str, Any]) -> V11ActionCase:
    subtype = value.get("agent_service_subtype")
    case = V11ActionCase(
        case_id=str(value["case_id"]),
        framework=str(value["framework"]),
        action_family=CanonicalActionFamily(str(value["action_family"])),
        logical_action_name=str(value["logical_action_name"]),
        argument_schema=_schema(dict(value["argument_schema"])),
        arguments=dict(value["arguments"]),
        effect_semantics=str(value["effect_semantics"]),
        scenario=str(value["scenario"]),
        operation_id=str(value["operation_id"]),
        capability=str(value["capability"]),
        agent_id=int(value["agent_id"]),
        agent_capability=str(value["agent_capability"]),
        agent_service_subtype=AgentServiceSubtype(str(subtype)) if subtype else None,
        continuation=dict(value.get("continuation", {})),
        placement=str(value.get("placement", "EXTERNAL")),
        development_fixture=True,
    ).validate()
    if value.get("public_profile_id") != PROFILE_ID:
        raise ValueError("case does not use the frozen V11.4 public profile")
    if _expected_effect(case) != case.effect_semantics:
        raise ValueError("manifest effect semantics disagree with the frozen canonical route")
    return case


def load_semantic_case(manifest_case: dict[str, Any]) -> V11ActionCase:
    if manifest_case.get("manifest_kind") not in {"S1_SOURCE_TOOL", "S2_COMPOSITION", "S4_EFFECT_CONTRACT"}:
        raise ValueError("unknown semantic manifest kind")
    return load_action(manifest_case)


def load_trajectory_case(manifest_case: dict[str, Any]) -> TrajectorySpec:
    if manifest_case.get("manifest_kind") != "S3_CAUSAL_TRAJECTORY":
        raise ValueError("unknown trajectory manifest kind")
    actions = tuple(load_action(dict(item)) for item in manifest_case["actions"])
    if not actions or len(actions) > 50:
        raise ValueError("trajectory action count is outside the frozen profile")
    if any(case.framework != manifest_case["framework"] for case in actions):
        raise ValueError("trajectory framework mismatch")
    return TrajectorySpec(
        str(manifest_case["trajectory_id"]),
        str(manifest_case["framework"]),
        str(manifest_case["workflow"]),
        actions,
        int(manifest_case.get("pir_delay_ms", 0)),
        int(manifest_case.get("decision_delay_ms", 0)),
    )


def load_structural_arm(manifest_arm: dict[str, Any]) -> TrajectorySpec:
    if manifest_arm.get("manifest_kind") != "STRUCTURAL_ARM":
        raise ValueError("unknown structural manifest kind")
    actions = tuple(load_action(dict(item)) for item in manifest_arm["actions"])
    if len(actions) > 50:
        raise ValueError("structural arm exceeds frozen operation capacity")
    return TrajectorySpec(
        str(manifest_arm["arm_id"]),
        str(manifest_arm["framework"]),
        str(manifest_arm["workflow"]),
        actions,
        int(manifest_arm.get("pir_delay_ms", 0)),
        int(manifest_arm.get("decision_delay_ms", 0)),
    )


def run_native_semantic_case(case: V11ActionCase, permit: ExecutionPermit):
    permit.require([case])
    return run_framework_case(case, native_implementation)


def run_canonical_semantic_case(
    case: V11ActionCase,
    output: Path,
    permit: ExecutionPermit,
    *,
    runner_binary: Path = GO_RUNNER,
):
    permit.require([case])
    with CanonicalOnlineSession(output, [case], runner_binary=runner_binary, public_profile=selected_profile(10, 3000)) as session:
        return run_framework_case(case, session.implementation())


def run_native_trajectory_case(spec: TrajectorySpec, permit: ExecutionPermit) -> dict[str, Any]:
    permit.require(spec.actions)
    return run_online_framework_workflow(spec.framework, spec.workflow, list(spec.actions), native_implementation)


def run_canonical_online_trajectory_case(
    spec: TrajectorySpec,
    output: Path,
    permit: ExecutionPermit,
    *,
    runner_binary: Path = GO_RUNNER,
) -> dict[str, Any]:
    permit.require(spec.actions)
    profile = selected_profile(10, 3000)
    with CanonicalOnlineSession(
        output,
        list(spec.actions),
        runner_binary=runner_binary,
        public_profile=profile,
        pir_delay_ms=spec.pir_delay_ms,
        decision_delay_ms=spec.decision_delay_ms,
    ) as session:
        semantic = run_online_framework_workflow(spec.framework, spec.workflow, list(spec.actions), session.implementation())
    structural, size = session.public_projections()
    return {
        "semantic": semantic,
        "raw_trace": session.trace,
        "strict_structural_projection": structural,
        "strict_size_projection": size,
        "causal_proof": session.causal_proof(),
    }


def run_structural_arm(
    spec: TrajectorySpec,
    output: Path,
    permit: ExecutionPermit,
    *,
    runner_binary: Path = GO_RUNNER,
) -> dict[str, Any]:
    value = run_canonical_online_trajectory_case(spec, output, permit, runner_binary=runner_binary)
    trace = value["raw_trace"]
    profile = selected_profile(10, 3000)
    value["strict_structural_projection"] = structural_projection(trace, profile)
    value["strict_size_projection"] = size_projection(trace, profile)
    value["structural_prefixes"] = {
        str(rounds): structural_prefix(value["strict_structural_projection"], rounds)
        for rounds in (1, 10, 50, 100, 200, 300, 356)
    }
    return value
