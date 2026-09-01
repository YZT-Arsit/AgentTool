from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    OPENAI_NATIVE_MAX_TURNS_PUBLIC,
)

from .isolated_tasks import (
    AUXILIARY_REGISTRY_COMPOSITE,
    FRAMEWORKS,
    PrimaryTimingWorkload,
    build_primary_workload,
    workload_manifest,
)
from .matched_tasks import public_profile_signature
from .profile import (
    TimingIndistinguishabilityProfile,
    delta_functional_candidate_profiles,
)
from .projection import expected_raw_timing_widths

PROTOCOL_BASE_SHA = "3dde92221b274148f4926de4d4df07d8a6c64cd5"
P10_PROFILE_ID = "V12-TIMING-INDIST-V3-H50-H4500-P10-PIR60"
SENTINEL_STAGE = "SENTINEL"
SENTINEL_TOTAL_BLOCKS = 300
SENTINEL_TRAIN_BLOCKS = 180
SENTINEL_EVAL_BLOCKS = 120
SENTINEL_SESSIONS_PER_COORDINATE = 600
SENTINEL_PHYSICAL_COORDINATES = 8
SENTINEL_OBSERVER_COMPARISONS = 10
SENTINEL_BOOTSTRAP_RESAMPLES = 10_000
SENTINEL_RANDOMIZATION_RESAMPLES = 10_000
SENTINEL_EARLY_FAIL_MARGIN = 0.55
SENTINEL_LCB_QUANTILE = 0.005
SENTINEL_TASKS = (
    AUXILIARY_REGISTRY_COMPOSITE,
    "T4",
    "T7",
    "T9",
)
SEED_LABEL = "V12-P10-TIMING-SENTINEL-DEVELOPMENT-20260831"


@dataclass(frozen=True)
class SentinelCoordinate:
    task_id: str
    framework: str
    observers: tuple[str, ...]

    @property
    def coordinate_id(self) -> str:
        framework_code = "OA" if self.framework == "OpenAI Agents SDK" else "MS"
        return f"P10-{self.task_id}-{framework_code}"


def p10_profile() -> TimingIndistinguishabilityProfile:
    profile = next(
        value for value in delta_functional_candidate_profiles() if value.round_period_ms == 10
    )
    if profile.profile_id != P10_PROFILE_ID or profile.total_rounds != 506:
        raise AssertionError("frozen P10 profile drifted")
    return profile


def physical_coordinates() -> tuple[SentinelCoordinate, ...]:
    observers = {
        AUXILIARY_REGISTRY_COMPOSITE: ("REGISTRY",),
        "T4": ("RELAY",),
        "T7": ("REGISTRY", "RELAY"),
        "T9": ("RELAY",),
    }
    return tuple(
        SentinelCoordinate(task, framework, observers[task])
        for task in SENTINEL_TASKS
        for framework in FRAMEWORKS
    )


def _digest(*values: object) -> bytes:
    material = "|".join(str(value) for value in values).encode()
    return hashlib.sha256(material).digest()


def coordinate_seed(coordinate: SentinelCoordinate, purpose: str) -> int:
    return int.from_bytes(
        _digest(SEED_LABEL, PROTOCOL_BASE_SHA, coordinate.coordinate_id, purpose)[:8], "big"
    )


def build_sentinel_workload(
    task_id: str, framework: str, label: int, *, block: int
) -> PrimaryTimingWorkload:
    return build_primary_workload(
        task_id,
        framework,
        label,
        block=block,
        stage=SENTINEL_STAGE,
        delta_ms=10,
    )


def _partition_by_block(coordinate: SentinelCoordinate) -> dict[int, str]:
    ordered = sorted(
        range(SENTINEL_TOTAL_BLOCKS),
        key=lambda block: _digest(
            SEED_LABEL, PROTOCOL_BASE_SHA, coordinate.coordinate_id, "PARTITION", block
        ),
    )
    train = set(ordered[:SENTINEL_TRAIN_BLOCKS])
    return {
        block: "SENTINEL_TRAIN" if block in train else "SENTINEL_EVAL"
        for block in range(SENTINEL_TOTAL_BLOCKS)
    }


def _class_order(coordinate: SentinelCoordinate, block: int) -> tuple[int, int]:
    first = int.from_bytes(
        _digest(SEED_LABEL, PROTOCOL_BASE_SHA, coordinate.coordinate_id, "PAIR_ORDER", block)[:8],
        "big",
    ) % 2
    return (first, 1 - first)


def _outer_coordinate_order(block: int) -> tuple[SentinelCoordinate, ...]:
    return tuple(
        sorted(
            physical_coordinates(),
            key=lambda coordinate: _digest(
                SEED_LABEL,
                PROTOCOL_BASE_SHA,
                "OUTER_ORDER",
                block,
                coordinate.coordinate_id,
            ),
        )
    )


def _framework_iteration_budget(framework: str) -> int:
    if framework == "OpenAI Agents SDK":
        return OPENAI_NATIVE_MAX_TURNS_PUBLIC
    if framework == "Microsoft Agent Framework":
        return MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC
    raise ValueError("unknown framework")


def build_freeze_manifest(
    *, execution_source_commit: str, analysis_hashes: Mapping[str, str]
) -> dict[str, Any]:
    profile = p10_profile()
    public_signature = public_profile_signature(profile)
    coordinates: list[dict[str, Any]] = []
    identities: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    for coordinate in physical_coordinates():
        partition = _partition_by_block(coordinate)
        coordinate_rows = []
        for block in range(SENTINEL_TOTAL_BLOCKS):
            members = [
                build_sentinel_workload(
                    coordinate.task_id, coordinate.framework, label, block=block
                )
                for label in (0, 1)
            ]
            member_rows = []
            for workload in members:
                row = workload_manifest(workload)
                row.update(
                    {
                        "coordinate_id": coordinate.coordinate_id,
                        "partition": partition[block],
                        "public_profile_signature": public_signature,
                        "framework_public_iteration_budget": _framework_iteration_budget(
                            coordinate.framework
                        ),
                        "session_count": 1,
                    }
                )
                encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                row["workload_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
                if workload.identity in identities:
                    raise AssertionError("duplicate frozen sentinel identity")
                identities[workload.identity] = row
                member_rows.append(row)
            if member_rows[0]["public_profile_signature"] != member_rows[1]["public_profile_signature"]:
                raise AssertionError("matched sentinel pair changed its public profile")
            order = _class_order(coordinate, block)
            pair = {
                "pair_id": hashlib.sha256(
                    f"{SEED_LABEL}|{coordinate.coordinate_id}|B{block}".encode()
                ).hexdigest()[:24],
                "coordinate_id": coordinate.coordinate_id,
                "task_id": coordinate.task_id,
                "framework": coordinate.framework,
                "block": block,
                "partition": partition[block],
                "class_execution_order": list(order),
                "member_identities_in_execution_order": [
                    members[label].identity for label in order
                ],
            }
            pairs.append(pair)
            coordinate_rows.append(pair["pair_id"])
        coordinates.append(
            {
                "coordinate_id": coordinate.coordinate_id,
                "task_id": coordinate.task_id,
                "framework": coordinate.framework,
                "observers": list(coordinate.observers),
                "total_blocks": SENTINEL_TOTAL_BLOCKS,
                "train_blocks": sum(
                    value == "SENTINEL_TRAIN" for value in partition.values()
                ),
                "eval_blocks": sum(
                    value == "SENTINEL_EVAL" for value in partition.values()
                ),
                "sessions": SENTINEL_SESSIONS_PER_COORDINATE,
                "pair_ids": coordinate_rows,
                "analysis_seed": coordinate_seed(coordinate, "MODEL_SELECTION"),
                "bootstrap_seed": coordinate_seed(coordinate, "BOOTSTRAP"),
                "randomization_seed": coordinate_seed(coordinate, "RANDOMIZATION"),
            }
        )

    pair_index = {(row["coordinate_id"], row["block"]): row for row in pairs}
    schedule: list[dict[str, Any]] = []
    for block in range(SENTINEL_TOTAL_BLOCKS):
        for coordinate in _outer_coordinate_order(block):
            pair = pair_index[(coordinate.coordinate_id, block)]
            for within_pair_index, identity in enumerate(
                pair["member_identities_in_execution_order"]
            ):
                schedule.append(
                    {
                        "execution_ordinal": len(schedule),
                        "coordinate_id": coordinate.coordinate_id,
                        "pair_id": pair["pair_id"],
                        "block": block,
                        "partition": pair["partition"],
                        "within_pair_index": within_pair_index,
                        "identity": identity,
                    }
                )
    manifest: dict[str, Any] = {
        "schema": "AgentTool.V12P10TimingSentinelFreeze/1",
        "phase": "V12-P10-TIMING-SENTINEL-DEVELOPMENT",
        "protocol_base_sha": PROTOCOL_BASE_SHA,
        "execution_source_commit": execution_source_commit,
        "frozen_before_first_protected_session": True,
        "seed_search": False,
        "identity_search": False,
        "seed_label": SEED_LABEL,
        "profile": profile.public_schema(),
        "public_profile_signature": public_signature,
        "tasks": {
            AUXILIARY_REGISTRY_COMPOSITE: "COMPOSITE_REGISTRY_RESOLUTION_PATTERN",
            "T4": "REPEATED_TARGET_PATTERN",
            "T7": "TOOL_VERSUS_AGENT_AS_TOOL_COMPOSITE",
            "T9": "PROVIDER_READINESS",
        },
        "physical_coordinates": coordinates,
        "physical_coordinate_count": len(coordinates),
        "observer_comparison_count": sum(len(row["observers"]) for row in coordinates),
        "blocks_per_physical_coordinate": SENTINEL_TOTAL_BLOCKS,
        "train_blocks_per_physical_coordinate": SENTINEL_TRAIN_BLOCKS,
        "eval_blocks_per_physical_coordinate": SENTINEL_EVAL_BLOCKS,
        "sessions_per_physical_coordinate": SENTINEL_SESSIONS_PER_COORDINATE,
        "total_physical_sessions": len(schedule),
        "pairs": pairs,
        "identity_manifest": identities,
        "execution_schedule": schedule,
        "feature_contract": {
            "view": "TIMING_ONLY_VIEW",
            "absolute_wall_clock_feature": False,
            "experiment_ordinal_feature": False,
            "block_id_feature": False,
            "RELAY_raw_widths": list(
                expected_raw_timing_widths(
                    "RELAY", public_r=506, public_q=100, has_relay_send=True
                )
            ),
            "REGISTRY_raw_widths": list(
                expected_raw_timing_widths(
                    "REGISTRY", public_r=506, public_q=100, has_registry_send=True
                )
            ),
        },
        "statistical_protocol": {
            "model_family": [
                "LOGISTIC_REGRESSION",
                "EXTRA_TREES",
                "HIST_GRADIENT_BOOSTING",
                "RBF_SVM",
            ],
            "model_selection": "TRAIN_ONLY",
            "score_orientation": "TRAIN_ONLY",
            "preprocessing": "TRAIN_ONLY",
            "decisive_eval_model_count": 1,
            "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
            "bootstrap_resamples": SENTINEL_BOOTSTRAP_RESAMPLES,
            "refit_inside_bootstrap": False,
            "lcb_quantile": SENTINEL_LCB_QUANTILE,
            "early_fail_rule": "ANY observer comparison LCB99.5 > 0.55",
            "privacy_pass_authority": False,
        },
        "analysis_hashes": dict(sorted(analysis_hashes.items())),
        "retry_policy": "ZERO_RETRY_ZERO_REPLACEMENT",
        "outlier_policy": "RETAIN_ALL_COMPLETE_SESSIONS_NO_TRIMMING_NO_WINSORIZATION",
        "sentinel_reuse": "PERMANENTLY_PROHIBITED",
        "P10_full": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "P20_P25": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "timing_confirmatory_sessions": 0,
        "final_v12_cases_executed": 0,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    validate_freeze_manifest(manifest)
    return manifest


def validate_freeze_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest["protocol_base_sha"] != PROTOCOL_BASE_SHA:
        raise ValueError("sentinel protocol base drifted")
    if int(manifest["physical_coordinate_count"]) != SENTINEL_PHYSICAL_COORDINATES:
        raise ValueError("sentinel physical coordinate count drifted")
    if int(manifest["observer_comparison_count"]) != SENTINEL_OBSERVER_COMPARISONS:
        raise ValueError("sentinel observer comparison count drifted")
    if int(manifest["total_physical_sessions"]) != 4800:
        raise ValueError("sentinel physical session denominator drifted")
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    if len(identities) != 4800 or len(schedule) != 4800:
        raise ValueError("sentinel identity manifest is incomplete")
    scheduled = [str(row["identity"]) for row in schedule]
    if len(set(scheduled)) != 4800 or set(scheduled) != set(identities):
        raise ValueError("sentinel schedule does not use every frozen identity exactly once")
    coordinates = manifest["physical_coordinates"]
    if any(
        (int(row["total_blocks"]), int(row["train_blocks"]), int(row["eval_blocks"]), int(row["sessions"]))
        != (300, 180, 120, 600)
        for row in coordinates
    ):
        raise ValueError("sentinel coordinate denominator drifted")
    pairs = manifest["pairs"]
    if len(pairs) != 2400:
        raise ValueError("sentinel pair inventory is incomplete")
    for pair in pairs:
        members = pair["member_identities_in_execution_order"]
        labels = [int(identities[identity]["label"]) for identity in members]
        if sorted(labels) != [0, 1]:
            raise ValueError("sentinel pair lost one protected class")
        signatures = [identities[identity]["public_profile_signature"] for identity in members]
        if signatures[0] != signatures[1]:
            raise ValueError("sentinel pair public signature mismatch")
