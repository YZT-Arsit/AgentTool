from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, replace

from v11_full_scope.fixtures import agent_case, tool_case, with_readiness
from v11_full_scope.models import AgentServiceSubtype, V11ActionCase


TASKS = {
    "T1": "PIR_AGENT_SELECTION_FREQUENCY",
    "T2": "AGENT_IDENTITY",
    "T3": "TOOL_ACTION_IDENTITY",
    "T4": "REPEATED_TARGET_LINKABILITY",
    "T5": "RARE_TARGET",
    "T6": "TRANSITION_ORDER",
    "T7": "ACTION_KIND",
    "T8": "INTERNAL_EXTERNAL_ROUTING",
    "T9": "PROVIDER_READINESS",
    "T10": "CAUSAL_DEPTH_PRIVATE_RESOLUTION_PATTERN",
}


@dataclass(frozen=True)
class TimingWorkflow:
    workflow_id: str
    block: int
    orthogonal_row: int
    framework: str
    workflow: str
    labels: dict[str, int]
    cases: tuple[V11ActionCase, ...]


def _labels(row: int) -> dict[str, int]:
    if not 0 <= row < 16:
        raise ValueError("orthogonal timing row must be in [0, 15]")
    return {
        task: ((row & column).bit_count() & 1)
        for task, column in zip(TASKS, range(1, 11), strict=True)
    }


def _op(profile_period: int, block: int, row: int, index: int) -> str:
    return f"opTD{profile_period:02d}B{block:03d}R{row:02d}A{index:02d}"


def _tool(
    identity: str,
    framework: str,
    operation_id: str,
    *,
    logical_name: str,
    effect: str = "READ_ONLY",
    agent_id: int = 10,
    agent_capability: str = "agent.tools",
) -> V11ActionCase:
    capability = {
        "READ_ONLY": "tool.read",
        "IDEMPOTENT_EFFECT": "tool.idem",
        "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
    }[effect]
    return replace(
        tool_case(identity, framework, effect_semantics=effect),
        operation_id=operation_id,
        logical_action_name=logical_name,
        capability=capability,
        agent_id=agent_id,
        agent_capability=agent_capability,
    ).validate()


def build_workflow(profile_period: int, block: int, row: int) -> TimingWorkflow:
    labels = _labels(row)
    framework = "OpenAI Agents SDK" if (block + row) % 2 == 0 else "Microsoft Agent Framework"
    base = f"DEV-TD-P{profile_period}-B{block:03d}-R{row:02d}"
    cases: list[V11ActionCase] = []

    def tool(segment: str, **kwargs: object) -> V11ActionCase:
        index = len(cases)
        value = _tool(
            f"{base}-A{index:02d}",
            framework,
            _op(profile_period, block, row, index),
            logical_name=str(kwargs.pop("logical_name", f"timing_{segment}_{index}")),
            **kwargs,
        )
        cases.append(value)
        return value

    for index in range(2 if labels["T1"] == 0 else 8):
        tool("frequency", logical_name=f"frequency_target_{index}")
    tool(
        "agent_identity",
        logical_name="agent_selected_tool",
        agent_id=10 if labels["T2"] == 0 else 21,
        agent_capability="agent.tools" if labels["T2"] == 0 else "agent.workflow.21",
    )
    tool("tool_identity", logical_name="private_target", effect="READ_ONLY" if labels["T3"] == 0 else "IDEMPOTENT_EFFECT")
    for index in range(4):
        tool("repetition", logical_name="repeated_target" if labels["T4"] == 0 else f"varied_target_{index}")
    for index in range(4):
        rare = labels["T5"] == 1 and index == 3
        tool("rare", logical_name="seeded_rare_target" if rare else "common_target", effect="IDEMPOTENT_EFFECT" if rare else "READ_ONLY")
    transition: list[V11ActionCase] = []
    for name, effect in (("transition_a", "READ_ONLY"), ("transition_b", "IDEMPOTENT_EFFECT")):
        index = len(cases) + len(transition)
        transition.append(
            _tool(
                f"{base}-A{index:02d}", framework, _op(profile_period, block, row, index),
                logical_name=name, effect=effect,
            )
        )
    cases.extend(transition if labels["T6"] == 0 else list(reversed(transition)))
    if labels["T7"] == 0:
        tool("action_kind", logical_name="private_action_kind")
    else:
        index = len(cases)
        cases.append(
            replace(
                agent_case(f"{base}-A{index:02d}", framework, AgentServiceSubtype.AGENT_AS_TOOL),
                operation_id=_op(profile_period, block, row, index),
                logical_action_name="private_action_kind",
            ).validate()
        )
    if labels["T8"] == 0:
        index = len(cases)
        cases.append(
            replace(
                agent_case(
                    f"{base}-A{index:02d}", framework,
                    AgentServiceSubtype.DIRECT_AGENT_SERVICE,
                    placement="TRUSTED_MODULE_LOCAL",
                ),
                operation_id=_op(profile_period, block, row, index),
                logical_action_name="private_internal_external",
            ).validate()
        )
    else:
        tool("internal_external", logical_name="private_internal_external")
    readiness_index = len(cases)
    readiness = _tool(
        f"{base}-A{readiness_index:02d}", framework,
        _op(profile_period, block, row, readiness_index),
        logical_name="provider_readiness",
    )
    cases.append(with_readiness(readiness, "EARLY_READY" if labels["T9"] == 0 else "LATE_READY_WITHIN_BOUND"))
    for index in range(2 if labels["T10"] == 0 else 10):
        tool("causal_depth", logical_name=f"causal_step_{index}")
    if len(cases) > 50:
        raise AssertionError("orthogonal timing workflow exceeds M=50")
    return TimingWorkflow(base, block, row, framework, "DYNAMIC_SEQUENCE", labels, tuple(cases))


def frozen_order(*, profile_period: int, blocks: int, seed_hex: str) -> list[TimingWorkflow]:
    seed = int(hashlib.sha256(f"{seed_hex}|P{profile_period}".encode()).hexdigest(), 16)
    generator = random.Random(seed)
    order: list[TimingWorkflow] = []
    for block in range(blocks):
        rows = list(range(16))
        generator.shuffle(rows)
        order.extend(build_workflow(profile_period, block, row) for row in rows)
    return order


def workflow_manifest(value: TimingWorkflow) -> dict[str, object]:
    return {
        "workflow_id": value.workflow_id,
        "block": value.block,
        "orthogonal_row": value.orthogonal_row,
        "framework": value.framework,
        "workflow": value.workflow,
        "secret_labels": value.labels,
        "operation_ids": [case.operation_id for case in value.cases],
        "logical_action_names": [case.logical_action_name for case in value.cases],
        "action_families": [case.action_family.value for case in value.cases],
        "effect_semantics": [case.effect_semantics for case in value.cases],
        "agent_ids": [case.agent_id for case in value.cases],
        "placements": [case.placement for case in value.cases],
        "argument_signature_sha256": hashlib.sha256(
            json.dumps([case.arguments for case in value.cases], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
