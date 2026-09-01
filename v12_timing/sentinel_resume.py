from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    OPENAI_NATIVE_MAX_TURNS_PUBLIC,
)

from .isolated_tasks import (
    AUXILIARY_REGISTRY_COMPOSITE,
    PrimaryTimingWorkload,
    build_primary_workload,
    workload_manifest,
)
from .matched_tasks import public_profile_signature
from .projection import expected_raw_timing_widths
from .sentinel import (
    P10_PROFILE_ID,
    PROTOCOL_BASE_SHA,
    SENTINEL_BOOTSTRAP_RESAMPLES,
    SENTINEL_LCB_QUANTILE,
    SENTINEL_OBSERVER_COMPARISONS,
    SENTINEL_PHYSICAL_COORDINATES,
    SentinelCoordinate,
    p10_profile,
    physical_coordinates,
)

LATEST_DEVELOPMENT_EVIDENCE_SHA = "da87c792ffacb7964446ab369768dd48d8ef997f"
PRIOR_RCA_SHA = "53a62b42340b6e041b72e8be2be2a134f303a4de"
ORIGINAL_ABORT_SHA = "f063d8bec6696f003020b1b6dab71e918e073aac"
IMMUTABLE_FAILED_IDENTITY = "DEV-TAD-P10-T7-MS-SENTINEL-B0075-C1"

RESUME_SEED_LABEL = "V12-P10-TIMING-DISTINGUISHABILITY-SENTINEL-RESUME-20260901"
WORKLOAD_BLOCK_OFFSET = 5000
PLANNED_BLOCKS = 315
PLANNED_TRAIN_BLOCKS = 189
PLANNED_EVAL_BLOCKS = 126
TARGET_TRAIN_COMPLETE_BLOCKS = 180
TARGET_EVAL_COMPLETE_BLOCKS = 120
SESSIONS_PER_COORDINATE = 630
TOTAL_SESSIONS = 5040
FAILURE_RATE_DIFFERENCE_MARGIN = 0.01
FAILURE_EXACT_ALPHA = 0.05 / 8
OPERATIONAL_FAILURE_RATE_MARGIN = 0.02


def _digest(*values: object) -> bytes:
    return hashlib.sha256("|".join(str(value) for value in values).encode()).digest()


def coordinate_seed(coordinate: SentinelCoordinate, purpose: str) -> int:
    return int.from_bytes(
        _digest(
            RESUME_SEED_LABEL,
            PROTOCOL_BASE_SHA,
            coordinate.coordinate_id,
            purpose,
        )[:8],
        "big",
    )


def build_resume_workload(
    task_id: str, framework: str, label: int, *, planned_block: int
) -> PrimaryTimingWorkload:
    if not 0 <= planned_block < PLANNED_BLOCKS:
        raise ValueError("resume sentinel planned block is outside the frozen denominator")
    return build_primary_workload(
        task_id,
        framework,
        label,
        block=WORKLOAD_BLOCK_OFFSET + planned_block,
        stage="SENTINEL",
        delta_ms=10,
    )


def _partition_by_block(coordinate: SentinelCoordinate) -> dict[int, str]:
    ordered = sorted(
        range(PLANNED_BLOCKS),
        key=lambda block: _digest(
            RESUME_SEED_LABEL,
            PROTOCOL_BASE_SHA,
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


def _selection_priority(
    coordinate: SentinelCoordinate, partition: Mapping[int, str]
) -> dict[int, int]:
    output: dict[int, int] = {}
    for partition_name in ("SENTINEL_TRAIN", "SENTINEL_EVAL"):
        blocks = [block for block, value in partition.items() if value == partition_name]
        ordered = sorted(
            blocks,
            key=lambda block: _digest(
                RESUME_SEED_LABEL,
                PROTOCOL_BASE_SHA,
                coordinate.coordinate_id,
                "COMPLETE_BLOCK_PRIORITY",
                partition_name,
                block,
            ),
        )
        output.update({block: rank for rank, block in enumerate(ordered)})
    return output


def _class_order(coordinate: SentinelCoordinate, planned_block: int) -> tuple[int, int]:
    first = int.from_bytes(
        _digest(
            RESUME_SEED_LABEL,
            PROTOCOL_BASE_SHA,
            coordinate.coordinate_id,
            "PAIR_ORDER",
            planned_block,
        )[:8],
        "big",
    ) % 2
    return first, 1 - first


def _outer_coordinate_order(planned_block: int) -> tuple[SentinelCoordinate, ...]:
    return tuple(
        sorted(
            physical_coordinates(),
            key=lambda coordinate: _digest(
                RESUME_SEED_LABEL,
                PROTOCOL_BASE_SHA,
                "OUTER_ORDER",
                planned_block,
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
    *,
    execution_source_commit: str,
    analysis_hashes: Mapping[str, str],
    excluded_identities: Sequence[str],
    exclusion_sources: Mapping[str, str],
) -> dict[str, Any]:
    profile = p10_profile()
    public_signature = public_profile_signature(profile)
    excluded = {str(value) for value in excluded_identities}
    coordinates: list[dict[str, Any]] = []
    identities: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    for coordinate in physical_coordinates():
        partition = _partition_by_block(coordinate)
        priority = _selection_priority(coordinate, partition)
        coordinate_pairs: list[str] = []
        for planned_block in range(PLANNED_BLOCKS):
            members = [
                build_resume_workload(
                    coordinate.task_id,
                    coordinate.framework,
                    label,
                    planned_block=planned_block,
                )
                for label in (0, 1)
            ]
            for workload in members:
                row = workload_manifest(workload)
                row.update(
                    {
                        "coordinate_id": coordinate.coordinate_id,
                        "planned_block": planned_block,
                        "partition": partition[planned_block],
                        "selection_priority": priority[planned_block],
                        "public_profile_signature": public_signature,
                        "framework_public_iteration_budget": _framework_iteration_budget(
                            coordinate.framework
                        ),
                        "session_count": 1,
                    }
                )
                encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                row["workload_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
                if workload.identity in identities or workload.identity in excluded:
                    raise AssertionError("resume sentinel identity is duplicated or excluded")
                identities[workload.identity] = row
            order = _class_order(coordinate, planned_block)
            pair_id = hashlib.sha256(
                f"{RESUME_SEED_LABEL}|{coordinate.coordinate_id}|B{planned_block}".encode()
            ).hexdigest()[:24]
            pair = {
                "pair_id": pair_id,
                "coordinate_id": coordinate.coordinate_id,
                "task_id": coordinate.task_id,
                "framework": coordinate.framework,
                "planned_block": planned_block,
                "workload_block": WORKLOAD_BLOCK_OFFSET + planned_block,
                "partition": partition[planned_block],
                "selection_priority": priority[planned_block],
                "class_execution_order": list(order),
                "member_identities_in_execution_order": [
                    members[label].identity for label in order
                ],
            }
            pairs.append(pair)
            coordinate_pairs.append(pair_id)
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
                "pair_ids": coordinate_pairs,
                "analysis_seed": coordinate_seed(coordinate, "MODEL_SELECTION"),
                "bootstrap_seed": coordinate_seed(coordinate, "BOOTSTRAP"),
                "randomization_seed": coordinate_seed(coordinate, "RANDOMIZATION"),
            }
        )

    pair_index = {(row["coordinate_id"], row["planned_block"]): row for row in pairs}
    schedule: list[dict[str, Any]] = []
    for planned_block in range(PLANNED_BLOCKS):
        for coordinate in _outer_coordinate_order(planned_block):
            pair = pair_index[(coordinate.coordinate_id, planned_block)]
            for within_pair_index, identity in enumerate(
                pair["member_identities_in_execution_order"]
            ):
                schedule.append(
                    {
                        "execution_ordinal": len(schedule),
                        "coordinate_id": coordinate.coordinate_id,
                        "pair_id": pair["pair_id"],
                        "planned_block": planned_block,
                        "workload_block": pair["workload_block"],
                        "partition": pair["partition"],
                        "selection_priority": pair["selection_priority"],
                        "within_pair_index": within_pair_index,
                        "identity": identity,
                    }
                )

    manifest: dict[str, Any] = {
        "schema": "AgentTool.V12P10TimingSentinelResumeFreeze/1",
        "phase": "V12-P10-TIMING-DISTINGUISHABILITY-SENTINEL-RESUME",
        "latest_development_evidence_sha": LATEST_DEVELOPMENT_EVIDENCE_SHA,
        "prior_rca_sha": PRIOR_RCA_SHA,
        "original_abort_sha": ORIGINAL_ABORT_SHA,
        "protocol_base_sha": PROTOCOL_BASE_SHA,
        "execution_source_commit": execution_source_commit,
        "frozen_before_first_protected_session": True,
        "seed_search": False,
        "identity_search": False,
        "seed_label": RESUME_SEED_LABEL,
        "workload_block_offset": WORKLOAD_BLOCK_OFFSET,
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
            "view": "TIMING_ONLY_VIEW",
            "absolute_wall_clock_feature": False,
            "experiment_ordinal_feature": False,
            "block_id_feature": False,
            "failure_status_feature": False,
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
        "completion_protocol": {
            "all_planned_sessions_included": True,
            "paired_exact_unit": "DISCORDANT_MATCHED_BLOCK",
            "failure_channel_flag": "absolute rate difference > 0.01 AND exact two-sided p < 0.05/8",
            "operational_concern": "either class failure rate > 0.02",
        },
        "analysis_hashes": dict(sorted(analysis_hashes.items())),
        "development_exclusions": {
            "immutable_failed_identity": IMMUTABLE_FAILED_IDENTITY,
            "old_complete_sessions_sealed": 1203,
            "old_incomplete_sessions_sealed": 1,
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
        "sentinel_reuse": "PERMANENTLY_PROHIBITED",
        "P10_full": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "P20_P25": "NOT_AUTHORIZED_IN_THIS_PHASE",
        "timing_confirmatory_sessions": 0,
        "final_v12_cases_executed": 0,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    validate_freeze_manifest(manifest, excluded_identities=excluded)
    return manifest


def validate_freeze_manifest(
    manifest: Mapping[str, Any], *, excluded_identities: Sequence[str] = ()
) -> None:
    payload = dict(manifest)
    claimed_payload_sha256 = str(payload.pop("payload_sha256", ""))
    actual_payload_sha256 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if claimed_payload_sha256 != actual_payload_sha256:
        raise ValueError("resume sentinel frozen manifest payload hash drifted")
    if manifest["protocol_base_sha"] != PROTOCOL_BASE_SHA:
        raise ValueError("resume sentinel protocol base drifted")
    if manifest["latest_development_evidence_sha"] != LATEST_DEVELOPMENT_EVIDENCE_SHA:
        raise ValueError("resume sentinel development lineage drifted")
    if manifest["profile"]["profile_id"] != P10_PROFILE_ID:
        raise ValueError("resume sentinel P10 profile drifted")
    if int(manifest["physical_coordinate_count"]) != SENTINEL_PHYSICAL_COORDINATES:
        raise ValueError("resume sentinel physical coordinate count drifted")
    if int(manifest["observer_comparison_count"]) != SENTINEL_OBSERVER_COMPARISONS:
        raise ValueError("resume sentinel observer comparison count drifted")
    if int(manifest["total_physical_sessions"]) != TOTAL_SESSIONS:
        raise ValueError("resume sentinel physical session denominator drifted")
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    if len(identities) != TOTAL_SESSIONS or len(schedule) != TOTAL_SESSIONS:
        raise ValueError("resume sentinel identity manifest is incomplete")
    scheduled = [str(row["identity"]) for row in schedule]
    if len(set(scheduled)) != TOTAL_SESSIONS or set(scheduled) != set(identities):
        raise ValueError("resume sentinel schedule does not use every identity exactly once")
    if set(identities) & {str(value) for value in excluded_identities}:
        raise ValueError("resume sentinel reuses an excluded identity")
    if IMMUTABLE_FAILED_IDENTITY in identities:
        raise ValueError("immutable failed identity was reintroduced")
    coordinates = manifest["physical_coordinates"]
    if any(
        (
            int(row["planned_blocks"]),
            int(row["planned_train_blocks"]),
            int(row["planned_eval_blocks"]),
            int(row["sessions"]),
        )
        != (PLANNED_BLOCKS, PLANNED_TRAIN_BLOCKS, PLANNED_EVAL_BLOCKS, SESSIONS_PER_COORDINATE)
        for row in coordinates
    ):
        raise ValueError("resume sentinel coordinate denominator drifted")
    pairs = manifest["pairs"]
    if len(pairs) != SENTINEL_PHYSICAL_COORDINATES * PLANNED_BLOCKS:
        raise ValueError("resume sentinel pair inventory is incomplete")
    for pair in pairs:
        members = pair["member_identities_in_execution_order"]
        rows = [identities[identity] for identity in members]
        if sorted(int(row["label"]) for row in rows) != [0, 1]:
            raise ValueError("resume sentinel pair lost one protected class")
        if rows[0]["public_profile_signature"] != rows[1]["public_profile_signature"]:
            raise ValueError("resume sentinel pair public signature mismatch")
        if any(int(row["planned_block"]) != int(pair["planned_block"]) for row in rows):
            raise ValueError("resume sentinel pair planned-block mapping drifted")


def exact_paired_binomial_two_sided(class0_failed_only: int, class1_failed_only: int) -> float:
    left = int(class0_failed_only)
    right = int(class1_failed_only)
    if left < 0 or right < 0:
        raise ValueError("discordant counts cannot be negative")
    total = left + right
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, value) for value in range(min(left, right) + 1))
    return min(1.0, 2.0 * tail / float(2**total))


@dataclass(frozen=True)
class CompletionCoordinate:
    coordinate_id: str
    class0_total: int
    class1_total: int
    class0_failures: int
    class1_failures: int
    complete_matched_blocks: int
    class0_failed_class1_complete: int
    class0_complete_class1_failed: int
    both_failed_blocks: int
    paired_exact_two_sided_p: float
    failure_channel_flag: bool
    operational_reliability_concern: bool

    def as_dict(self) -> dict[str, Any]:
        class0_rate = self.class0_failures / self.class0_total
        class1_rate = self.class1_failures / self.class1_total
        return {
            **self.__dict__,
            "class0_failure_rate": class0_rate,
            "class1_failure_rate": class1_rate,
            "absolute_failure_rate_difference": abs(class0_rate - class1_rate),
            "asymmetric_incomplete_blocks": self.class0_failed_class1_complete
            + self.class0_complete_class1_failed,
        }


def completion_channel(
    manifest: Mapping[str, Any], status_by_identity: Mapping[str, str]
) -> list[dict[str, Any]]:
    identities = manifest["identity_manifest"]
    if set(status_by_identity) != set(identities):
        raise ValueError("completion channel must include every planned identity exactly once")
    if set(status_by_identity.values()) - {"COMPLETE", "FAILED"}:
        raise ValueError("completion channel status must be COMPLETE or FAILED")
    output: list[dict[str, Any]] = []
    for coordinate in manifest["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
        class_failures = [0, 0]
        complete = left = right = both = 0
        for pair in pairs:
            members = pair["member_identities_in_execution_order"]
            by_label = {int(identities[identity]["label"]): identity for identity in members}
            failed0 = status_by_identity[by_label[0]] == "FAILED"
            failed1 = status_by_identity[by_label[1]] == "FAILED"
            class_failures[0] += failed0
            class_failures[1] += failed1
            if not failed0 and not failed1:
                complete += 1
            elif failed0 and not failed1:
                left += 1
            elif not failed0 and failed1:
                right += 1
            else:
                both += 1
        p_value = exact_paired_binomial_two_sided(left, right)
        rate0 = class_failures[0] / PLANNED_BLOCKS
        rate1 = class_failures[1] / PLANNED_BLOCKS
        result = CompletionCoordinate(
            coordinate_id=coordinate_id,
            class0_total=PLANNED_BLOCKS,
            class1_total=PLANNED_BLOCKS,
            class0_failures=class_failures[0],
            class1_failures=class_failures[1],
            complete_matched_blocks=complete,
            class0_failed_class1_complete=left,
            class0_complete_class1_failed=right,
            both_failed_blocks=both,
            paired_exact_two_sided_p=p_value,
            failure_channel_flag=(
                abs(rate0 - rate1) > FAILURE_RATE_DIFFERENCE_MARGIN
                and p_value < FAILURE_EXACT_ALPHA
            ),
            operational_reliability_concern=(
                rate0 > OPERATIONAL_FAILURE_RATE_MARGIN
                or rate1 > OPERATIONAL_FAILURE_RATE_MARGIN
            ),
        )
        output.append(result.as_dict())
    return output


def select_complete_blocks(
    manifest: Mapping[str, Any], status_by_identity: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    identities = manifest["identity_manifest"]
    if set(status_by_identity) != set(identities):
        raise ValueError("complete-block selection requires the full completion inventory")
    output: dict[str, dict[str, Any]] = {}
    for coordinate in manifest["physical_coordinates"]:
        coordinate_id = str(coordinate["coordinate_id"])
        pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
        selected: dict[str, Any] = {}
        for partition, target in (
            ("SENTINEL_TRAIN", TARGET_TRAIN_COMPLETE_BLOCKS),
            ("SENTINEL_EVAL", TARGET_EVAL_COMPLETE_BLOCKS),
        ):
            complete_pairs = [
                pair
                for pair in pairs
                if pair["partition"] == partition
                and all(
                    status_by_identity[identity] == "COMPLETE"
                    for identity in pair["member_identities_in_execution_order"]
                )
            ]
            complete_pairs.sort(
                key=lambda row: (int(row["selection_priority"]), int(row["planned_block"]))
            )
            chosen = complete_pairs[:target]
            selected[partition] = {
                "available_complete_blocks": len(complete_pairs),
                "target_complete_blocks": target,
                "sufficient": len(complete_pairs) >= target,
                "selected_planned_blocks": [int(row["planned_block"]) for row in chosen],
                "selected_pair_ids": [str(row["pair_id"]) for row in chosen],
                "selected_identities": [
                    str(identity)
                    for row in chosen
                    for identity in row["member_identities_in_execution_order"]
                ],
            }
        output[coordinate_id] = selected
    return output
