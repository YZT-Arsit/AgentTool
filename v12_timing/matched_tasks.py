from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Mapping

from .isolated_tasks import FRAMEWORKS, PrimaryTimingWorkload, build_primary_workload
from .profile import TimingIndistinguishabilityProfile

PRIMARY_TASKS = tuple(f"T{index}" for index in range(2, 11))
PRIMARY_ISOLATED_TASKS = ("T2", "T3", "T4", "T5", "T6", "T9")
PRIMARY_COMPOSITE_TASKS = ("T7", "T8", "T10")
AUXILIARY_REGISTRY_COMPOSITE = "C1_REGISTRY_RESOLUTION_PATTERN"
SENTINEL_COMPARISONS = (AUXILIARY_REGISTRY_COMPOSITE, "T4", "T7", "T9")
T1_PRIMARY_ISOLATION = "NOT_FEASIBLE"
PAIR_PRIVATE_FIELDS = frozenset({"pair_id", "label", "task_id", "framework", "partition"})


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    changed_factor: str
    fixed_factors: tuple[str, ...]
    expected_private_runtime_differences: tuple[str, ...]
    public_profile_equality_requirements: tuple[str, ...]
    applicable_frameworks: tuple[str, ...]
    observers: tuple[str, ...]
    estimand: str = "ISOLATED"


PUBLIC_EQUALITY_FIELDS = (
    "admission_horizon_ms", "round_period_ms", "total_rounds",
    "request_final_bytes", "response_final_bytes", "pir_resolution_opportunities",
    "pir_public_epoch_ms", "pir_resolution_period_ms", "ohttp_key_id", "kem_id",
    "kdf_id", "aead_id", "config_epoch", "connection_policy", "session_count",
    "maximum_real_operations",
)

COMMON_FIXED = ("public profile", "framework", "pair block", "semantic arguments", "effect semantics")
TASK_DEFINITIONS = {
    "T2": TaskDefinition("T2", "private Agent identity", COMMON_FIXED,
                         ("descriptor/cache selection",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS,
                         ("REGISTRY", "RELAY")),
    "T3": TaskDefinition("T3", "private Tool/action identity", COMMON_FIXED + ("Agent identity",),
                         ("private action dispatch",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS, ("RELAY",)),
    "T4": TaskDefinition("T4", "repeated versus distinct target pattern", COMMON_FIXED + ("count",),
                         ("target reuse pattern",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS, ("RELAY",)),
    "T5": TaskDefinition("T5", "common versus one predeclared rare target", COMMON_FIXED + ("count",),
                         ("one private target identity",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS, ("RELAY",)),
    "T6": TaskDefinition("T6", "private transition order", COMMON_FIXED + ("action multiset", "count"),
                         ("execution order",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS, ("RELAY",)),
    "T7": TaskDefinition("T7", "ordinary Tool versus Agent-as-Tool", COMMON_FIXED + ("count",),
                         ("action family", "descriptor/dispatch mechanism"), PUBLIC_EQUALITY_FIELDS,
                         FRAMEWORKS, ("REGISTRY", "RELAY"), "COMPOSITE"),
    "T8": TaskDefinition("T8", "trusted-local versus external mediated route", COMMON_FIXED + ("count",),
                         ("placement", "route and action-family mechanism"), PUBLIC_EQUALITY_FIELDS,
                         FRAMEWORKS, ("REGISTRY", "RELAY"), "COMPOSITE"),
    "T9": TaskDefinition("T9", "early-ready versus late-ready-within-bound", COMMON_FIXED + ("count",),
                         ("provider completion timing",), PUBLIC_EQUALITY_FIELDS, FRAMEWORKS, ("RELAY",)),
    "T10": TaskDefinition("T10", "private causal depth/count", COMMON_FIXED,
                          ("action count", "causal depth", "private work volume"), PUBLIC_EQUALITY_FIELDS,
                          FRAMEWORKS, ("RELAY",), "COMPOSITE"),
}


@dataclass(frozen=True)
class MatchedPair:
    pair_id: str
    task_id: str
    framework: str
    block: int
    members: tuple[PrimaryTimingWorkload, PrimaryTimingWorkload]

    def validate(self) -> "MatchedPair":
        if self.task_id not in PRIMARY_TASKS or self.framework not in FRAMEWORKS:
            raise ValueError("unsupported primary matched-pair coordinate")
        if len(self.members) != 2 or {item.label for item in self.members} != {0, 1}:
            raise ValueError("matched pair must contain exactly one member of each class")
        for item in self.members:
            if (item.task_id, item.framework, item.block) != (self.task_id, self.framework, self.block):
                raise ValueError("matched pair member coordinate mismatch")
        return self


def build_matched_pair(task_id: str, framework: str, *, block: int, stage: str,
                       delta_ms: int, seed_hex: str) -> MatchedPair:
    if task_id == "T1":
        raise ValueError("T1 primary isolation is not feasible under the frozen cache semantics")
    if task_id not in PRIMARY_TASKS or framework not in FRAMEWORKS:
        raise ValueError("invalid primary matched-pair coordinate")
    members = [build_primary_workload(task_id, framework, label, block=block, stage=stage,
                                      delta_ms=delta_ms) for label in (0, 1)]
    material = f"{seed_hex}|{task_id}|{framework}|{stage}|{delta_ms}|{block}"
    digest = hashlib.sha256(material.encode()).hexdigest()
    random.Random(int(digest, 16)).shuffle(members)
    return MatchedPair(f"PAIR-{digest[:20]}", task_id, framework, block,
                       (members[0], members[1])).validate()


def public_profile_signature(profile: TimingIndistinguishabilityProfile) -> dict[str, Any]:
    return {field: getattr(profile, field) for field in PUBLIC_EQUALITY_FIELDS}


def verify_pair_public_profile_equality(pair: MatchedPair, profiles: Mapping[int, TimingIndistinguishabilityProfile]) -> bool:
    pair.validate()
    signatures = [public_profile_signature(profiles[item.label]) for item in pair.members]
    return signatures[0] == signatures[1]


def task_definition_manifest() -> dict[str, Any]:
    return {
        task_id: {
            "changed_factor": value.changed_factor,
            "fixed_factors": list(value.fixed_factors),
            "expected_private_runtime_differences": list(value.expected_private_runtime_differences),
            "public_profile_equality_requirements": list(value.public_profile_equality_requirements),
            "applicable_frameworks": list(value.applicable_frameworks),
            "observers": list(value.observers),
            "estimand": value.estimand,
        }
        for task_id, value in TASK_DEFINITIONS.items()
    }


def timing_task_protocol_manifest() -> dict[str, Any]:
    return {
        "primary": task_definition_manifest(),
        "primary_isolated_tasks": list(PRIMARY_ISOLATED_TASKS),
        "primary_composite_tasks": list(PRIMARY_COMPOSITE_TASKS),
        "auxiliary_registry_composite": {
            "task_id": AUXILIARY_REGISTRY_COMPOSITE,
            "historical_construction": "T1_REGISTRY_REAL_RESOLUTION_PATTERN",
            "estimand": "COMPOSITE",
            "changed_factors": [
                "legitimate real descriptor-resolution pattern",
                "private Agent identity pattern",
                "trusted descriptor-cache behavior",
            ],
            "public_schedule": "fixed Q=100 under one public profile",
            "causal_attribution": False,
        },
        "sentinel_comparisons": list(SENTINEL_COMPARISONS),
    }
