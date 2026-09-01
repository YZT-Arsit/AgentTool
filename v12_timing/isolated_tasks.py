from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass, replace

from v11_full_scope.fixtures import agent_case, tool_case, with_readiness
from v11_full_scope.models import AgentServiceSubtype, V11ActionCase

TASKS = {
    "T1": "REGISTRY_REAL_RESOLUTION_PATTERN",
    "T2": "PRIVATE_AGENT_IDENTITY",
    "T3": "TOOL_ACTION_IDENTITY",
    "T4": "REPEATED_TARGET_LINKABILITY",
    "T5": "RARE_TARGET",
    "T6": "TRANSITION_ORDER",
    "T7": "ACTION_KIND",
    "T8": "INTERNAL_EXTERNAL_ROUTING",
    "T9": "PROVIDER_READINESS",
    "T10": "PRIVATE_COUNT_CAUSAL_DEPTH",
}

SENTINEL_TASKS = ("T1", "T4", "T7", "T9")
AUXILIARY_REGISTRY_COMPOSITE = "C1_REGISTRY_RESOLUTION_PATTERN"
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")
CLAIM_OBSERVERS = {
    "T1": ("REGISTRY",),
    "T2": ("REGISTRY", "RELAY"),
    "T3": ("RELAY",),
    "T4": ("RELAY",),
    "T5": ("RELAY",),
    "T6": ("RELAY",),
    "T7": ("REGISTRY", "RELAY"),
    "T8": ("REGISTRY", "RELAY"),
    "T9": ("RELAY",),
    "T10": ("RELAY",),
    AUXILIARY_REGISTRY_COMPOSITE: ("REGISTRY",),
}


@dataclass(frozen=True)
class PrimaryTimingWorkload:
    identity: str
    task_id: str
    task: str
    framework: str
    label: int
    block: int
    stage: str
    delta_ms: int
    workflow: str
    cases: tuple[V11ActionCase, ...]

    @property
    def claim_observers(self) -> tuple[str, ...]:
        return CLAIM_OBSERVERS[self.task_id]


def _framework_code(framework: str) -> str:
    return "OA" if framework == "OpenAI Agents SDK" else "MS"


def _operation_id(delta_ms: int, task_id: str, framework: str, stage: str, block: int, label: int, index: int) -> str:
    task_number = 1 if task_id == AUXILIARY_REGISTRY_COMPOSITE else int(task_id[1:])
    stage_code = {"CONTROL": "C", "SENTINEL": "S", "FULL": "F"}[stage]
    return f"opTA{delta_ms:02d}{task_number:02d}{_framework_code(framework)}{stage_code}{block:04d}{label}{index:02d}"


def _base_identity(delta_ms: int, task_id: str, framework: str, stage: str, block: int, label: int) -> str:
    return f"DEV-TAD-P{delta_ms}-{task_id}-{_framework_code(framework)}-{stage}-B{block:04d}-C{label}"


def _tool(
    base: str,
    framework: str,
    operation_id: str,
    *,
    logical_name: str,
    agent_id: int = 10,
    agent_capability: str = "agent.tools",
    readiness: str = "DEFAULT",
) -> V11ActionCase:
    value = replace(
        tool_case(f"{base}-{logical_name}", framework),
        operation_id=operation_id,
        logical_action_name=logical_name,
        agent_id=agent_id,
        agent_capability=agent_capability,
        capability="tool.read",
    ).validate()
    return value if readiness == "DEFAULT" else with_readiness(value, readiness).validate()


def _agent_tool(base: str, framework: str, operation_id: str, *, logical_name: str) -> V11ActionCase:
    return replace(
        agent_case(f"{base}-{logical_name}", framework, AgentServiceSubtype.AGENT_AS_TOOL),
        operation_id=operation_id,
        logical_action_name=logical_name,
    ).validate()


def _internal(base: str, framework: str, operation_id: str, *, logical_name: str) -> V11ActionCase:
    return replace(
        agent_case(
            f"{base}-{logical_name}",
            framework,
            AgentServiceSubtype.DIRECT_AGENT_SERVICE,
            placement="TRUSTED_MODULE_LOCAL",
        ),
        operation_id=operation_id,
        logical_action_name=logical_name,
    ).validate()


def build_primary_workload(
    task_id: str,
    framework: str,
    label: int,
    *,
    block: int,
    stage: str,
    delta_ms: int,
) -> PrimaryTimingWorkload:
    if task_id not in TASKS and task_id != AUXILIARY_REGISTRY_COMPOSITE:
        raise ValueError("invalid isolated timing workload coordinate")
    if framework not in FRAMEWORKS or label not in (0, 1):
        raise ValueError("invalid isolated timing workload coordinate")
    if stage not in {"CONTROL", "SENTINEL", "FULL"}:
        raise ValueError("invalid isolated timing stage")
    base = _base_identity(delta_ms, task_id, framework, stage, block, label)
    cases: list[V11ActionCase] = []

    def op(index: int) -> str:
        return _operation_id(delta_ms, task_id, framework, stage, block, label, index)

    workflow = "DYNAMIC_SEQUENCE"
    construction_task_id = "T1" if task_id == AUXILIARY_REGISTRY_COMPOSITE else task_id
    if construction_task_id == "T1":
        for index in range(6):
            if label == 0 or index % 2 == 0:
                cases.append(_tool(base, framework, op(index), logical_name=f"resolution_step_{index}"))
            else:
                cases.append(
                    _tool(
                        base,
                        framework,
                        op(index),
                        logical_name=f"resolution_step_{index}",
                        agent_id=21,
                        agent_capability="agent.workflow.21",
                    )
                )
    elif construction_task_id == "T2":
        for index in range(6):
            cases.append(
                _tool(
                    base,
                    framework,
                    op(index),
                    logical_name=f"identity_matched_step_{index}",
                    agent_id=10 if label == 0 else 21,
                    agent_capability="agent.tools" if label == 0 else "agent.workflow.21",
                )
            )
    elif construction_task_id == "T3":
        target = "private_tool_alpha" if label == 0 else "private_tool_beta"
        cases = [_tool(base, framework, op(index), logical_name=target) for index in range(6)]
    elif construction_task_id == "T4":
        cases = [
            _tool(
                base,
                framework,
                op(index),
                logical_name="repeated_private_target" if label == 0 else f"distinct_private_target_{index}",
            )
            for index in range(10)
        ]
    elif construction_task_id == "T5":
        cases = [
            _tool(
                base,
                framework,
                op(index),
                logical_name=("rare_private_target" if label == 1 and index == 7 else "common_private_target"),
            )
            for index in range(10)
        ]
    elif construction_task_id == "T6":
        names = ("transition_a", "transition_b") if label == 0 else ("transition_b", "transition_a")
        cases = [_tool(base, framework, op(index), logical_name=name) for index, name in enumerate(names)]
    elif construction_task_id == "T7":
        first = _tool(base, framework, op(0), logical_name="action_kind_anchor")
        if label == 0:
            cases = [first, _tool(base, framework, op(1), logical_name="matched_action_target")]
        else:
            cases = [first, _agent_tool(base, framework, op(1), logical_name="matched_action_target")]
            workflow = "TOOL_TO_AGENT_AS_TOOL"
    elif construction_task_id == "T8":
        if label == 0:
            cases = [_internal(base, framework, op(index), logical_name=f"matched_route_step_{index}") for index in range(4)]
        else:
            cases = [_tool(base, framework, op(index), logical_name=f"matched_route_step_{index}") for index in range(4)]
    elif construction_task_id == "T9":
        readiness = "EARLY_READY" if label == 0 else "LATE_READY_WITHIN_BOUND"
        cases = [
            _tool(base, framework, op(index), logical_name=f"readiness_step_{index}", readiness=readiness)
            for index in range(10)
        ]
    elif construction_task_id == "T10":
        depth = 10 if label == 0 else 30
        cases = [_tool(base, framework, op(index), logical_name=f"causal_step_{index}") for index in range(depth)]
    else:  # pragma: no cover - exhaustive guard
        raise AssertionError(task_id)
    if len(cases) > 50:
        raise AssertionError("isolated timing workload exceeds M=50")
    task_name = (
        "REGISTRY_RESOLUTION_PATTERN_COMPOSITE"
        if task_id == AUXILIARY_REGISTRY_COMPOSITE
        else TASKS[task_id]
    )
    return PrimaryTimingWorkload(base, task_id, task_name, framework, label, block, stage, delta_ms, workflow, tuple(cases))


def randomized_pair_order(
    task_id: str,
    framework: str,
    *,
    block: int,
    stage: str,
    delta_ms: int,
    seed_hex: str,
) -> tuple[PrimaryTimingWorkload, PrimaryTimingWorkload]:
    values = [
        build_primary_workload(task_id, framework, label, block=block, stage=stage, delta_ms=delta_ms)
        for label in (0, 1)
    ]
    seed_material = f"{seed_hex}|P{delta_ms}|{task_id}|{framework}|{stage}|B{block}".encode()
    random.Random(int(hashlib.sha256(seed_material).hexdigest(), 16)).shuffle(values)
    return values[0], values[1]


def workload_manifest(value: PrimaryTimingWorkload) -> dict[str, object]:
    return {
        "identity": value.identity,
        "task_id": value.task_id,
        "task": value.task,
        "framework": value.framework,
        "label": value.label,
        "block": value.block,
        "stage": value.stage,
        "delta_ms": value.delta_ms,
        "workflow": value.workflow,
        "claim_observers": list(value.claim_observers),
        "operation_ids": [case.operation_id for case in value.cases],
        "logical_action_names": [case.logical_action_name for case in value.cases],
        "agent_ids": [case.agent_id for case in value.cases],
        "action_families": [case.action_family.value for case in value.cases],
        "placements": [case.placement for case in value.cases],
        "readiness_modes": [case.continuation.get("provider_readiness_mode", "DEFAULT") for case in value.cases],
        "argument_signature_sha256": hashlib.sha256(
            json.dumps([case.arguments for case in value.cases], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def task_isolation_audit(task_id: str, framework: str) -> dict[str, object]:
    left = workload_manifest(build_primary_workload(task_id, framework, 0, block=0, stage="CONTROL", delta_ms=10))
    right = workload_manifest(build_primary_workload(task_id, framework, 1, block=0, stage="CONTROL", delta_ms=10))
    differences = [
        key
        for key in (
            "workflow",
            "logical_action_names",
            "agent_ids",
            "action_families",
            "placements",
            "readiness_modes",
            "argument_signature_sha256",
        )
        if left[key] != right[key]
    ]
    allowed = {
        "T1": {"agent_ids"},
        "T2": {"agent_ids"},
        "T3": {"logical_action_names"},
        "T4": {"logical_action_names"},
        "T5": {"logical_action_names"},
        "T6": {"logical_action_names"},
        "T7": {"workflow", "agent_ids", "action_families", "argument_signature_sha256"},
        "T8": {"agent_ids", "action_families", "placements", "argument_signature_sha256"},
        "T9": {"readiness_modes"},
        "T10": {
            "logical_action_names",
            "agent_ids",
            "action_families",
            "placements",
            "readiness_modes",
            "argument_signature_sha256",
        },
        AUXILIARY_REGISTRY_COMPOSITE: {"agent_ids"},
    }[task_id]
    if task_id == "T10":
        differences.append("private_case_count")
    return {
        "task_id": task_id,
        "framework": framework,
        "observed_controlled_differences": sorted(set(differences)),
        "allowed_target_differences": sorted(allowed | ({"private_case_count"} if task_id == "T10" else set())),
        "pass": set(differences) == allowed | ({"private_case_count"} if task_id == "T10" else set()),
    }


def all_task_isolation_audits() -> Iterable[dict[str, object]]:
    for task_id in TASKS:
        for framework in FRAMEWORKS:
            yield task_isolation_audit(task_id, framework)
