from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    OPENAI_NATIVE_MAX_TURNS_PUBLIC,
)

from . import sentinel_resume as _sentinel_resume
from .isolated_tasks import (
    PrimaryTimingWorkload,
    build_primary_workload,
    workload_manifest,
)
from .matched_tasks import public_profile_signature
from .profile import duplex_timing_candidate_profiles
from .projection import expected_raw_timing_widths
from .sentinel import SentinelCoordinate

BASE_COST_ABORT_COMMIT = "b439fa72b87db29efc2b027c76c10a353dd6448d"
BASE_DUPLEX_EVIDENCE = "bf499d5e56507eb069d4998a2851cfaa23ec7fc6"
HISTORICAL_P10_RESULT_SHA = "558c97bd5ca8bb9123382800cb73eb410cab6342"
SMOKE_SEED_LABEL = "V12-DUPLEX-REPAIR-SMOKE-SENTINEL-20260902"
WORKLOAD_BLOCK_OFFSET = 30_000
PLANNED_BLOCKS = 64
PLANNED_TRAIN_BLOCKS = 32
PLANNED_EVAL_BLOCKS = 32
TARGET_TRAIN_COMPLETE_BLOCKS = 30
TARGET_EVAL_COMPLETE_BLOCKS = 30
SESSIONS_PER_COORDINATE = 128
TOTAL_SESSIONS = 640
SMOKE_LCB_QUANTILE = 0.05
SMOKE_FAILURE_MARGIN = 0.65
BOOTSTRAP_RESAMPLES = 10_000
RANDOMIZATION_RESAMPLES = 10_000

FAILURE_EXACT_ALPHA = _sentinel_resume.FAILURE_EXACT_ALPHA
FAILURE_RATE_DIFFERENCE_MARGIN = _sentinel_resume.FAILURE_RATE_DIFFERENCE_MARGIN
OPERATIONAL_FAILURE_RATE_MARGIN = _sentinel_resume.OPERATIONAL_FAILURE_RATE_MARGIN
completion_channel = _sentinel_resume.completion_channel
select_complete_blocks = _sentinel_resume.select_complete_blocks


def physical_coordinates() -> tuple[SentinelCoordinate, ...]:
    return (
        SentinelCoordinate(
            "C1_REGISTRY_RESOLUTION_PATTERN",
            "OpenAI Agents SDK",
            ("REGISTRY",),
        ),
        SentinelCoordinate(
            "T7",
            "OpenAI Agents SDK",
            ("REGISTRY", "RELAY"),
        ),
        SentinelCoordinate(
            "T7",
            "Microsoft Agent Framework",
            ("REGISTRY", "RELAY"),
        ),
        SentinelCoordinate(
            "T9",
            "OpenAI Agents SDK",
            ("RELAY",),
        ),
        SentinelCoordinate(
            "T9",
            "Microsoft Agent Framework",
            ("RELAY",),
        ),
    )


def _digest(*values: object) -> bytes:
    return hashlib.sha256("|".join(str(value) for value in values).encode()).digest()


def p10_profile():
    profile = next(
        value
        for value in duplex_timing_candidate_profiles()
        if value.round_period_ms == 10
    )
    if profile.total_rounds != 506:
        raise AssertionError("duplex smoke P10 profile drifted")
    return profile


def build_smoke_workload(
    task_id: str, framework: str, label: int, *, planned_block: int
) -> PrimaryTimingWorkload:
    if not 0 <= planned_block < PLANNED_BLOCKS:
        raise ValueError("smoke block is outside the frozen denominator")
    return build_primary_workload(
        task_id,
        framework,
        label,
        block=WORKLOAD_BLOCK_OFFSET + planned_block,
        stage="SENTINEL",
        delta_ms=10,
    )


def _partition(coordinate: SentinelCoordinate) -> dict[int, str]:
    ordered = sorted(
        range(PLANNED_BLOCKS),
        key=lambda block: _digest(
            SMOKE_SEED_LABEL, coordinate.coordinate_id, "PARTITION", block
        ),
    )
    train = set(ordered[:PLANNED_TRAIN_BLOCKS])
    return {
        block: "SENTINEL_TRAIN" if block in train else "SENTINEL_EVAL"
        for block in range(PLANNED_BLOCKS)
    }


def _priorities(
    coordinate: SentinelCoordinate, partition: Mapping[int, str]
) -> dict[int, int]:
    result: dict[int, int] = {}
    for name in ("SENTINEL_TRAIN", "SENTINEL_EVAL"):
        ordered = sorted(
            (block for block, value in partition.items() if value == name),
            key=lambda block: _digest(
                SMOKE_SEED_LABEL,
                coordinate.coordinate_id,
                "COMPLETE_BLOCK_PRIORITY",
                name,
                block,
            ),
        )
        result.update({block: rank for rank, block in enumerate(ordered)})
    return result


def _class_order(coordinate: SentinelCoordinate, block: int) -> tuple[int, int]:
    first = (
        int.from_bytes(
            _digest(SMOKE_SEED_LABEL, coordinate.coordinate_id, "PAIR_ORDER", block)[
                :8
            ],
            "big",
        )
        % 2
    )
    return first, 1 - first


def _iteration_budget(framework: str) -> int:
    if framework == "OpenAI Agents SDK":
        return OPENAI_NATIVE_MAX_TURNS_PUBLIC
    if framework == "Microsoft Agent Framework":
        return MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC
    raise ValueError("unknown framework")


def coordinate_seed(coordinate: SentinelCoordinate, purpose: str) -> int:
    return int.from_bytes(
        _digest(SMOKE_SEED_LABEL, coordinate.coordinate_id, purpose)[:8], "big"
    )


def build_freeze_manifest(
    *,
    execution_source_commit: str,
    analysis_hashes: Mapping[str, str],
    excluded_identities: Sequence[str],
    exclusion_sources: Mapping[str, str],
) -> dict[str, Any]:
    profile = p10_profile()
    signature = public_profile_signature(profile)
    excluded = {str(value) for value in excluded_identities}
    identities: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    coordinates = []
    for coordinate in physical_coordinates():
        partition = _partition(coordinate)
        priorities = _priorities(coordinate, partition)
        pair_ids = []
        for block in range(PLANNED_BLOCKS):
            members = [
                build_smoke_workload(
                    coordinate.task_id, coordinate.framework, label, planned_block=block
                )
                for label in (0, 1)
            ]
            for workload in members:
                row = workload_manifest(workload)
                row.update(
                    {
                        "coordinate_id": coordinate.coordinate_id,
                        "planned_block": block,
                        "partition": partition[block],
                        "selection_priority": priorities[block],
                        "public_profile_signature": signature,
                        "framework_public_iteration_budget": _iteration_budget(
                            coordinate.framework
                        ),
                        "session_count": 1,
                    }
                )
                if workload.identity in identities or workload.identity in excluded:
                    raise AssertionError("smoke identity is reused")
                identities[workload.identity] = row
            order = _class_order(coordinate, block)
            pair_id = hashlib.sha256(
                f"{SMOKE_SEED_LABEL}|{coordinate.coordinate_id}|B{block}".encode()
            ).hexdigest()[:24]
            pairs.append(
                {
                    "pair_id": pair_id,
                    "coordinate_id": coordinate.coordinate_id,
                    "task_id": coordinate.task_id,
                    "framework": coordinate.framework,
                    "planned_block": block,
                    "workload_block": WORKLOAD_BLOCK_OFFSET + block,
                    "partition": partition[block],
                    "selection_priority": priorities[block],
                    "class_execution_order": list(order),
                    "member_identities_in_execution_order": [
                        members[label].identity for label in order
                    ],
                }
            )
            pair_ids.append(pair_id)
        coordinates.append(
            {
                "coordinate_id": coordinate.coordinate_id,
                "task_id": coordinate.task_id,
                "framework": coordinate.framework,
                "observers": list(coordinate.observers),
                "planned_blocks": PLANNED_BLOCKS,
                "planned_train_blocks": PLANNED_TRAIN_BLOCKS,
                "planned_eval_blocks": PLANNED_EVAL_BLOCKS,
                "target_train_complete_blocks": TARGET_TRAIN_COMPLETE_BLOCKS,
                "target_eval_complete_blocks": TARGET_EVAL_COMPLETE_BLOCKS,
                "sessions": SESSIONS_PER_COORDINATE,
                "pair_ids": pair_ids,
                "analysis_seed": coordinate_seed(coordinate, "MODEL_SELECTION"),
                "bootstrap_seed": coordinate_seed(coordinate, "BOOTSTRAP"),
                "randomization_seed": coordinate_seed(coordinate, "RANDOMIZATION"),
            }
        )
    pair_index = {(row["coordinate_id"], row["planned_block"]): row for row in pairs}
    schedule = []
    for block in range(PLANNED_BLOCKS):
        ordered_coordinates = sorted(
            physical_coordinates(),
            key=lambda coordinate: _digest(
                SMOKE_SEED_LABEL, "OUTER_ORDER", block, coordinate.coordinate_id
            ),
        )
        for coordinate in ordered_coordinates:
            pair = pair_index[(coordinate.coordinate_id, block)]
            for within_pair_index, identity in enumerate(
                pair["member_identities_in_execution_order"]
            ):
                schedule.append(
                    {
                        "execution_ordinal": len(schedule),
                        "coordinate_id": coordinate.coordinate_id,
                        "pair_id": pair["pair_id"],
                        "planned_block": block,
                        "workload_block": pair["workload_block"],
                        "partition": pair["partition"],
                        "selection_priority": pair["selection_priority"],
                        "within_pair_index": within_pair_index,
                        "identity": identity,
                    }
                )
    relay_widths = expected_raw_timing_widths(
        "RELAY", public_r=506, public_q=100, has_relay_duplex=True
    )
    registry_widths = expected_raw_timing_widths(
        "REGISTRY", public_r=506, public_q=100, has_registry_send=True
    )
    manifest: dict[str, Any] = {
        "schema": "AgentTool.V12DuplexRepairSmokeSentinelFreeze/1",
        "phase": "V12-DUPLEX-REPAIR-SMOKE-SENTINEL",
        "base_cost_abort_commit": BASE_COST_ABORT_COMMIT,
        "base_duplex_evidence": BASE_DUPLEX_EVIDENCE,
        "historical_p10_result_sha": HISTORICAL_P10_RESULT_SHA,
        "protocol_base_sha": BASE_COST_ABORT_COMMIT,
        "execution_source_commit": execution_source_commit,
        "frozen_before_first_session": True,
        "seed_search": False,
        "identity_search": False,
        "seed_label": SMOKE_SEED_LABEL,
        "workload_block_offset": WORKLOAD_BLOCK_OFFSET,
        "profile": profile.public_schema(),
        "public_profile_signature": signature,
        "physical_coordinates": coordinates,
        "physical_coordinate_count": 5,
        "observer_comparison_count": 7,
        "planned_blocks_per_coordinate": PLANNED_BLOCKS,
        "planned_train_blocks_per_coordinate": PLANNED_TRAIN_BLOCKS,
        "planned_eval_blocks_per_coordinate": PLANNED_EVAL_BLOCKS,
        "target_train_complete_blocks": TARGET_TRAIN_COMPLETE_BLOCKS,
        "target_eval_complete_blocks": TARGET_EVAL_COMPLETE_BLOCKS,
        "sessions_per_coordinate": SESSIONS_PER_COORDINATE,
        "total_physical_sessions": len(schedule),
        "pairs": pairs,
        "identity_manifest": identities,
        "execution_schedule": schedule,
        "complete_block_selection": "FIRST_COMPLETE_BY_FROZEN_PARTITION_PRIORITY",
        "feature_contract": {
            "RELAY_view": "DUPLEX_TIMING_ONLY_VIEW",
            "RELAY_raw_widths": list(relay_widths),
            "RELAY_feature_width": sum(relay_widths) + 12 * len(relay_widths) + 1,
            "REGISTRY_view": "TIMING_ONLY_VIEW",
            "REGISTRY_raw_widths": list(registry_widths),
            "REGISTRY_feature_width": sum(registry_widths)
            + 12 * len(registry_widths)
            + 1,
            "failure_status_feature": False,
            "private_semantic_feature": False,
        },
        "statistical_protocol": {
            "version": "V3.1_DUPLEX_REPAIR_SMOKE",
            "model_selection": "TRAIN_ONLY_FIVE_FOLD_BLOCK_CV",
            "score_orientation": "TRAIN_ONLY",
            "sklearn_random_state": "UINT64_MOD_2_POW_32",
            "model_family": [
                "LOGISTIC_REGRESSION",
                "EXTRA_TREES",
                "HIST_GRADIENT_BOOSTING",
                "RBF_SVM",
            ],
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "randomization_resamples": RANDOMIZATION_RESAMPLES,
            "lcb_quantile": SMOKE_LCB_QUANTILE,
            "failure_margin": SMOKE_FAILURE_MARGIN,
            "privacy_pass_authority": False,
        },
        "analysis_hashes": dict(sorted(analysis_hashes.items())),
        "development_exclusions": {
            "excluded_identity_count": len(excluded),
            "excluded_identity_inventory_sha256": hashlib.sha256(
                "\n".join(sorted(excluded)).encode()
            ).hexdigest(),
            "sources": dict(sorted(exclusion_sources.items())),
            "new_identity_overlap": 0,
        },
        "retry_policy": "ZERO_RETRY_ZERO_REPLACEMENT",
        "collection_first": True,
        "P10_full": "NOT_RUN",
        "P20_P25": "NOT_RUN",
        "confirmatory": "NOT_RUN",
        "final_holdout": "NOT_RUN",
    }
    manifest["payload_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    validate_freeze_manifest(manifest, excluded_identities=excluded)
    return manifest


def validate_freeze_manifest(
    manifest: Mapping[str, Any], *, excluded_identities: Sequence[str] = ()
) -> None:
    payload = dict(manifest)
    claimed = str(payload.pop("payload_sha256", ""))
    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if claimed != actual:
        raise ValueError("smoke manifest payload hash drifted")
    if manifest["schema"] != "AgentTool.V12DuplexRepairSmokeSentinelFreeze/1":
        raise ValueError("wrong smoke manifest schema")
    if int(manifest["physical_coordinate_count"]) != 5:
        raise ValueError("smoke physical coordinate count drifted")
    if int(manifest["observer_comparison_count"]) != 7:
        raise ValueError("smoke observer count drifted")
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    if len(identities) != TOTAL_SESSIONS or len(schedule) != TOTAL_SESSIONS:
        raise ValueError("smoke identity denominator drifted")
    if {row["identity"] for row in schedule} != set(identities):
        raise ValueError("smoke schedule is not identity-complete")
    if set(identities) & {str(value) for value in excluded_identities}:
        raise ValueError("smoke identity reuses development evidence")
    if int(manifest["feature_contract"]["RELAY_feature_width"]) != 5695:
        raise ValueError("smoke Relay feature width drifted")
    if int(manifest["feature_contract"]["REGISTRY_feature_width"]) != 448:
        raise ValueError("smoke Registry feature width drifted")
    if len(manifest["pairs"]) != 5 * PLANNED_BLOCKS:
        raise ValueError("smoke pair denominator drifted")
    for pair in manifest["pairs"]:
        rows = [
            identities[value] for value in pair["member_identities_in_execution_order"]
        ]
        if sorted(int(row["label"]) for row in rows) != [0, 1]:
            raise ValueError("smoke pair lost one class")
        if rows[0]["public_profile_signature"] != rows[1]["public_profile_signature"]:
            raise ValueError("smoke pair public profiles differ")
