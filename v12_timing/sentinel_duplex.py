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
from .sentinel import (
    SENTINEL_BOOTSTRAP_RESAMPLES,
    SENTINEL_EARLY_FAIL_MARGIN,
    SENTINEL_LCB_QUANTILE,
    SENTINEL_OBSERVER_COMPARISONS,
    SENTINEL_PHYSICAL_COORDINATES,
    SENTINEL_RANDOMIZATION_RESAMPLES,
    SentinelCoordinate,
    physical_coordinates,
)

FAILURE_EXACT_ALPHA = _sentinel_resume.FAILURE_EXACT_ALPHA
FAILURE_RATE_DIFFERENCE_MARGIN = _sentinel_resume.FAILURE_RATE_DIFFERENCE_MARGIN
OPERATIONAL_FAILURE_RATE_MARGIN = _sentinel_resume.OPERATIONAL_FAILURE_RATE_MARGIN
completion_channel = _sentinel_resume.completion_channel
select_complete_blocks = _sentinel_resume.select_complete_blocks

BASE_DUPLEX_EVIDENCE = "bf499d5e56507eb069d4998a2851cfaa23ec7fc6"
METHODOLOGY_BASE_SHA = "63792088161deb6b1ccd3c4b4cb28babbf72f3ec"
HISTORICAL_P10_RESULT_SHA = "558c97bd5ca8bb9123382800cb73eb410cab6342"
DUPLEX_P10_PROFILE_ID = "V12-TIMING-INDIST-V4R5-H50-H4500-P10-PIR60"
DUPLEX_SEED_LABEL = "V12-DUPLEX-P10-SENTINEL-20260902"
WORKLOAD_BLOCK_OFFSET = 20_000
PLANNED_BLOCKS = 315
PLANNED_TRAIN_BLOCKS = 189
PLANNED_EVAL_BLOCKS = 126
TARGET_TRAIN_COMPLETE_BLOCKS = 180
TARGET_EVAL_COMPLETE_BLOCKS = 120
SESSIONS_PER_COORDINATE = 630
TOTAL_SESSIONS = 5040


def _digest(*values: object) -> bytes:
    return hashlib.sha256("|".join(str(value) for value in values).encode()).digest()


def p10_profile():
    profile = next(
        value
        for value in duplex_timing_candidate_profiles()
        if value.round_period_ms == 10
    )
    if profile.profile_id != DUPLEX_P10_PROFILE_ID or profile.total_rounds != 506:
        raise AssertionError("duplex P10 public profile drifted")
    return profile


def coordinate_seed(coordinate: SentinelCoordinate, purpose: str) -> int:
    return int.from_bytes(
        _digest(
            DUPLEX_SEED_LABEL,
            BASE_DUPLEX_EVIDENCE,
            coordinate.coordinate_id,
            purpose,
        )[:8],
        "big",
    )


def build_duplex_workload(
    task_id: str, framework: str, label: int, *, planned_block: int
) -> PrimaryTimingWorkload:
    if not 0 <= planned_block < PLANNED_BLOCKS:
        raise ValueError("duplex sentinel block is outside the frozen denominator")
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
            DUPLEX_SEED_LABEL,
            BASE_DUPLEX_EVIDENCE,
            coordinate.coordinate_id,
            "PARTITION",
            block,
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
                DUPLEX_SEED_LABEL,
                BASE_DUPLEX_EVIDENCE,
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
            _digest(
                DUPLEX_SEED_LABEL,
                BASE_DUPLEX_EVIDENCE,
                coordinate.coordinate_id,
                "PAIR_ORDER",
                block,
            )[:8],
            "big",
        )
        % 2
    )
    return first, 1 - first


def _outer_order(block: int) -> tuple[SentinelCoordinate, ...]:
    return tuple(
        sorted(
            physical_coordinates(),
            key=lambda coordinate: _digest(
                DUPLEX_SEED_LABEL,
                BASE_DUPLEX_EVIDENCE,
                "OUTER_ORDER",
                block,
                coordinate.coordinate_id,
            ),
        )
    )


def _iteration_budget(framework: str) -> int:
    if framework == "OpenAI Agents SDK":
        return OPENAI_NATIVE_MAX_TURNS_PUBLIC
    if framework == "Microsoft Agent Framework":
        return MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC
    raise ValueError("unknown framework")


def build_freeze_manifest(
    *,
    execution_source_commit: str,
    analysis_hashes: Mapping[str, str],
    excluded_identities: Sequence[str],
    exclusion_sources: Mapping[str, str],
) -> dict[str, Any]:
    profile = p10_profile()
    public_signature = public_profile_signature(profile)
    excluded = {str(value) for value in excluded_identities}
    identities: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    coordinates: list[dict[str, Any]] = []
    for coordinate in physical_coordinates():
        partition = _partition(coordinate)
        priorities = _priorities(coordinate, partition)
        pair_ids: list[str] = []
        for block in range(PLANNED_BLOCKS):
            members = [
                build_duplex_workload(
                    coordinate.task_id,
                    coordinate.framework,
                    label,
                    planned_block=block,
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
                        "public_profile_signature": public_signature,
                        "framework_public_iteration_budget": _iteration_budget(
                            coordinate.framework
                        ),
                        "session_count": 1,
                    }
                )
                row["workload_manifest_sha256"] = hashlib.sha256(
                    json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                if workload.identity in identities or workload.identity in excluded:
                    raise AssertionError("duplex sentinel identity is reused")
                identities[workload.identity] = row
            order = _class_order(coordinate, block)
            pair_id = hashlib.sha256(
                f"{DUPLEX_SEED_LABEL}|{coordinate.coordinate_id}|B{block}".encode()
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
    schedule: list[dict[str, Any]] = []
    for block in range(PLANNED_BLOCKS):
        for coordinate in _outer_order(block):
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
        "schema": "AgentTool.V12DuplexP10SentinelFreeze/1",
        "phase": "V12-DUPLEX-P10-CANDIDATE-ELIGIBILITY-AND-SENTINEL",
        "base_duplex_evidence": BASE_DUPLEX_EVIDENCE,
        "methodology_base_sha": METHODOLOGY_BASE_SHA,
        "protocol_base_sha": BASE_DUPLEX_EVIDENCE,
        "historical_p10_result_sha": HISTORICAL_P10_RESULT_SHA,
        "execution_source_commit": execution_source_commit,
        "frozen_before_first_protected_session": True,
        "seed_search": False,
        "identity_search": False,
        "seed_label": DUPLEX_SEED_LABEL,
        "workload_block_offset": WORKLOAD_BLOCK_OFFSET,
        "profile": profile.public_schema(),
        "public_profile_signature": public_signature,
        "physical_coordinates": coordinates,
        "physical_coordinate_count": len(coordinates),
        "observer_comparison_count": sum(len(row["observers"]) for row in coordinates),
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
            "absolute_wall_clock_feature": False,
            "experiment_ordinal_feature": False,
            "block_id_feature": False,
            "failure_status_feature": False,
            "private_semantic_feature": False,
        },
        "statistical_protocol": {
            "version": "V3.1_DUPLEX_FEATURE_CONTRACT",
            "model_family": [
                "LOGISTIC_REGRESSION",
                "EXTRA_TREES",
                "HIST_GRADIENT_BOOSTING",
                "RBF_SVM",
            ],
            "model_selection": "TRAIN_ONLY",
            "score_orientation": "TRAIN_ONLY",
            "sklearn_random_state": "UINT64_MOD_2_POW_32",
            "decisive_eval_model_count": 1,
            "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
            "bootstrap_resamples": SENTINEL_BOOTSTRAP_RESAMPLES,
            "randomization_resamples": SENTINEL_RANDOMIZATION_RESAMPLES,
            "lcb_quantile": SENTINEL_LCB_QUANTILE,
            "early_fail_margin": SENTINEL_EARLY_FAIL_MARGIN,
            "privacy_pass_authority": False,
        },
        "completion_protocol": {
            "failure_exact_alpha": FAILURE_EXACT_ALPHA,
            "failure_rate_difference_margin": FAILURE_RATE_DIFFERENCE_MARGIN,
            "operational_failure_rate_margin": OPERATIONAL_FAILURE_RATE_MARGIN,
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
        "isolated_session_failure_policy": "RECORD_AND_CONTINUE_COMPLETION_CHANNEL",
        "common_integrity_failure_policy": "HARD_STOP",
        "outlier_policy": "RETAIN_ALL_COMPLETE_SESSIONS_NO_TRIMMING_NO_WINSORIZATION",
        "P10_full": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "P20_P25": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "timing_confirmatory_sessions": 0,
        "final_v12_cases_executed": 0,
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
        raise ValueError("duplex sentinel manifest payload hash drifted")
    if manifest["base_duplex_evidence"] != BASE_DUPLEX_EVIDENCE:
        raise ValueError("duplex evidence base drifted")
    if manifest["profile"]["profile_id"] != DUPLEX_P10_PROFILE_ID:
        raise ValueError("duplex P10 profile drifted")
    if int(manifest["physical_coordinate_count"]) != SENTINEL_PHYSICAL_COORDINATES:
        raise ValueError("duplex physical coordinate count drifted")
    if int(manifest["observer_comparison_count"]) != SENTINEL_OBSERVER_COMPARISONS:
        raise ValueError("duplex observer comparison count drifted")
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    if len(identities) != TOTAL_SESSIONS or len(schedule) != TOTAL_SESSIONS:
        raise ValueError("duplex identity denominator drifted")
    scheduled = [str(row["identity"]) for row in schedule]
    if len(set(scheduled)) != TOTAL_SESSIONS or set(scheduled) != set(identities):
        raise ValueError("duplex execution schedule is not one-use complete")
    if set(identities) & {str(value) for value in excluded_identities}:
        raise ValueError("duplex sentinel reuses an excluded identity")
    if tuple(manifest["feature_contract"]["RELAY_raw_widths"]) != (
        506,
        505,
        506,
        505,
        506,
        505,
        506,
        505,
        506,
        506,
        506,
    ):
        raise ValueError("duplex Relay feature widths drifted")
    if int(manifest["feature_contract"]["RELAY_feature_width"]) != 5695:
        raise ValueError("duplex Relay feature vector width drifted")
    if int(manifest["feature_contract"]["REGISTRY_feature_width"]) != 448:
        raise ValueError("duplex Registry feature vector width drifted")
    if len(manifest["pairs"]) != SENTINEL_PHYSICAL_COORDINATES * PLANNED_BLOCKS:
        raise ValueError("duplex matched-pair inventory drifted")
    for pair in manifest["pairs"]:
        rows = [
            identities[value] for value in pair["member_identities_in_execution_order"]
        ]
        if sorted(int(row["label"]) for row in rows) != [0, 1]:
            raise ValueError("duplex pair lost one class")
        if rows[0]["public_profile_signature"] != rows[1]["public_profile_signature"]:
            raise ValueError("duplex pair public profiles differ")
