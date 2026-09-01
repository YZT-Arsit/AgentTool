from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.canonical import _canonical_ids
from v12_timing.attack import BOOTSTRAP_RESAMPLES, FOLDS, frozen_models
from v12_timing.isolated_tasks import (
    CLAIM_OBSERVERS,
    FRAMEWORKS,
    SENTINEL_TASKS,
    TASKS,
    all_task_isolation_audits,
    build_primary_workload,
)
from v12_timing.profile import timing_attack_candidate_profiles
from v12_timing.projection import REGISTRY_ATTACK_TIMING_KEYS, RELAY_ATTACK_TIMING_KEYS


BASE_COMMIT = "1cf12990fdfc005f59ee6d31943c40db53c5408b"
CONTROL_BLOCKS = 100
SENTINEL_BLOCKS = 100
FULL_BLOCKS = 300


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def raw_widths() -> dict[str, object]:
    control: dict[str, object] = {"0": {}}
    for task_id in TASKS:
        workloads = [
            build_primary_workload(task_id, framework, label, block=0, stage="CONTROL", delta_ms=0)
            for framework in FRAMEWORKS
            for label in (0, 1)
        ]
        max_actions = max(len(value.cases) for value in workloads)
        max_agents = max(len({_canonical_ids(case)[0] for case in value.cases}) for value in workloads)
        control["0"][task_id] = {
            "RELAY": [max_actions, max_actions, max_actions - 1, max_actions - 1, max_actions],
            "REGISTRY": [max_agents, max_agents, max_agents - 1, max_agents],
        }
    protected: dict[str, object] = {}
    for profile in timing_attack_candidate_profiles():
        rounds = profile.total_rounds
        protected[str(profile.round_period_ms)] = {
            task_id: {
                "RELAY": [rounds, rounds, rounds - 1, rounds - 1, rounds],
                "REGISTRY": [100, 100, 99, 100],
            }
            for task_id in TASKS
        }
    return {"CONTROL": control, "PROTECTED": protected}


def auc_standard_error_at_chance(per_class: int) -> float:
    auc = 0.5
    q1 = auc / (2 - auc)
    q2 = 2 * auc * auc / (1 + auc)
    variance = (
        auc * (1 - auc)
        + (per_class - 1) * (q1 - auc * auc)
        + (per_class - 1) * (q2 - auc * auc)
    ) / (per_class * per_class)
    return math.sqrt(variance)


def functional_workloads(delta: int) -> list[dict[str, str]]:
    prefix = f"DEV-TAD-FUNCTIONAL-P{delta}"
    rows: list[dict[str, str]] = []
    for framework, code in (("OpenAI Agents SDK", "OA"), ("Microsoft Agent Framework", "MS")):
        rows.extend(
            [
                {"identity": f"{prefix}-{code}-DEPTH50-001", "framework": framework, "kind": "SAME_AGENT_CAUSAL_DEPTH_50"},
                {"identity": f"{prefix}-{code}-K6-001", "framework": framework, "kind": "MAX_K_DISTINCT_AGENT_RESOLUTIONS"},
                {"identity": f"{prefix}-{code}-AAT-001", "framework": framework, "kind": "AGENT_AS_TOOL_TRANSITION"},
                {"identity": f"{prefix}-{code}-CACHE30-001", "framework": framework, "kind": "SAME_AGENT_CACHE_HIT_30"},
            ]
        )
    return rows


def main() -> None:
    audits = list(all_task_isolation_audits())
    if not all(value["pass"] for value in audits):
        raise AssertionError(f"primary timing task isolation failed: {audits}")
    matrix_audit = {
        "schema": "AgentTool.V12TimingAttackMatrixAudit/1",
        "phase": "V12-TIMING-ATTACK-DEVELOPMENT-AND-PROFILE-SELECTION",
        "base_commit": BASE_COMMIT,
        "old_matrix": "AUXILIARY_ONLY_INVALID_FOR_PRIMARY_ML",
        "old_rows": 16,
        "independent_row_bits": 4,
        "derived_binary_labels": 10,
        "defect": "nonlinear attackers can infer one derived label through timing caused by other simultaneously varied labels",
        "primary_repair": "one task-isolated randomized pair per block; all non-target secret dimensions frozen",
        "outcome_dependent_reclassification": False,
        "pass": True,
    }
    write_json(ROOT / "V12_TIMING_ATTACK_MATRIX_AUDIT.json", matrix_audit)
    (ROOT / "V12_TIMING_ATTACK_MATRIX_AUDIT.md").write_text(
        "# V12 timing attack matrix audit\n\n"
        "The historical 16-row Walsh-Hadamard matrix derives ten labels from four independent row bits. "
        "Pairwise balance does not prevent nonlinear cross-label inference, so it is retained only as auxiliary "
        "factorial development evidence and is invalid for the primary decisive ML attack.\n\n"
        "The repaired primary design uses task-isolated binary pairs: each randomized block contains one class-0 "
        "and one class-1 session, with only the declared target dimension changed. Classification was fixed before "
        "new timing sessions.\n",
        encoding="utf-8",
        newline="\n",
    )
    projection_audit = {
        "schema": "AgentTool.V12TimingAttackProjectionAudit/1",
        "relay_attack_timing_fields": list(RELAY_ATTACK_TIMING_KEYS) + ["total_session_span_ns"],
        "registry_attack_timing_fields": list(REGISTRY_ATTACK_TIMING_KEYS) + ["total_resolution_session_span_ns"],
        "absolute_wall_clock": "EXCLUDED",
        "experiment_order": "EXCLUDED",
        "block_identity": "EXCLUDED",
        "operation_ids": "EXCLUDED",
        "agent_and_tool_identity": "EXCLUDED",
        "private_route_alias": "EXCLUDED",
        "real_dummy_labels": "EXCLUDED",
        "internal_result_readiness": "EXCLUDED",
        "scheduler_cpu_gc_cgroup_diagnostics": "EXCLUDED",
        "session_conditioning": "conditioned on public session existence; timestamps are relative to first observer-visible event",
        "pass": True,
    }
    write_json(ROOT / "V12_TIMING_ATTACK_PROJECTION_AUDIT.json", projection_audit)
    (ROOT / "V12_TIMING_ATTACK_PROJECTION_AUDIT.md").write_text(
        "# V12 timing attack projection audit\n\n"
        "The Relay classifier receives only within-session request/response timing, gaps, request-response "
        "durations, total span, and fixed public metadata. The Registry classifier receives only within-session "
        "query/response timing, gaps, total epoch span, and fixed public PIR metadata. Absolute time, execution "
        "order, randomized block ID, private identifiers, real/dummy labels, readiness state, and scheduler/host "
        "diagnostics are excluded. The claim is conditioned on a public session existing.\n",
        encoding="utf-8",
        newline="\n",
    )
    block_seed = sha_bytes(f"{BASE_COMMIT}|V12-TAD|BLOCK-RANDOMIZATION|NO-SEED-SEARCH".encode())
    model_seed = sha_bytes(f"{BASE_COMMIT}|V12-TAD|MODEL-SEEDS|NO-SEED-SEARCH".encode())
    profiles = [profile.public_schema() for profile in timing_attack_candidate_profiles()]
    se = auc_standard_error_at_chance(FULL_BLOCKS)
    protocol = {
        "schema": "AgentTool.V12TimingAttackDevelopmentProtocolFreeze/1",
        "phase": "V12-TIMING-ATTACK-DEVELOPMENT-AND-PROFILE-SELECTION",
        "base_commit": BASE_COMMIT,
        "source_hashes": {
            str(path).replace("\\", "/"): sha(ROOT / path)
            for path in (
                Path("v12_timing/profile.py"),
                Path("v12_timing/matrix.py"),
                Path("v12_timing/isolated_tasks.py"),
                Path("v12_timing/projection.py"),
                Path("v12_timing/attack.py"),
                Path("v12_timing/controls.py"),
                Path("v12_timing/development.py"),
                Path("v11_online/session.py"),
                Path("common_action_gateway_v2/canonicalv9/online.go"),
                Path("common_action_gateway_v2/canonicalv9/runner.go"),
                Path("scripts/run_v12_timing_attack_campaign.py"),
                Path("scripts/analyze_v12_timing_attack.py"),
                Path("scripts/run_v12_timing_v3_functional_capacity.py"),
            )
        },
        "causal_horizon_ms": 4500,
        "profiles": profiles,
        "profile_order_delta_ms": [10, 20, 25],
        "profile_selection_rule": "smallest functionally valid Delta passing all informative claim-bearing Stage-B attacks",
        "runtime_repairs_between_candidates": "PROHIBITED",
        "tasks": TASKS,
        "claim_observers": {key: list(value) for key, value in CLAIM_OBSERVERS.items()},
        "frameworks": list(FRAMEWORKS),
        "framework_pooling": "OPTIONAL_SECONDARY_NEVER_HIDES_WORST_FRAMEWORK",
        "task_isolation_audits": audits,
        "sentinel_tasks": list(SENTINEL_TASKS),
        "positive_control_blocks": CONTROL_BLOCKS,
        "sentinel_blocks": SENTINEL_BLOCKS,
        "full_blocks": FULL_BLOCKS,
        "sentinel_sessions_per_class_framework_profile": SENTINEL_BLOCKS,
        "full_sessions_per_class_framework_profile": FULL_BLOCKS,
        "sentinel_included_in_full_denominator": True,
        "sentinel_full_additional_blocks": [SENTINEL_BLOCKS, FULL_BLOCKS - 1],
        "full_nonsentinel_blocks": [0, FULL_BLOCKS - 1],
        "maximum_automatic_sessions_per_class": 1000,
        "block_randomization_seed_sha256": block_seed,
        "model_seed_sha256": model_seed,
        "seed_search": False,
        "model_family": list(frozen_models(1)),
        "statistics": {
            "cross_validation": f"{FOLDS}-fold StratifiedGroupKFold by randomized pair block",
            "bootstrap": "whole randomized pair blocks with replacement",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "chance_auc": 0.5,
            "protected_upper_ci_limit": 0.55,
            "positive_control_lower_ci_minimum": 0.60,
            "sentinel_early_fail": "best point AUC >= 0.60 OR lower 95% group CI > 0.55",
            "session_is_semantic_unit": True,
            "cell_independence_assumed": False,
        },
        "power": {
            "method": "Hanley-McNeil independent-session approximation used only for pre-execution denominator planning; decisive CI is paired-block bootstrap",
            "per_class": FULL_BLOCKS,
            "chance_auc_standard_error": se,
            "approximate_two_sided_95_half_width": 1.96 * se,
            "conclusion": "300/class is retained as the frozen minimum; no protected-outcome sample extension is permitted",
        },
        "feature_set": {
            "absolute_wall_clock": "EXCLUDED",
            "experiment_order": "EXCLUDED",
            "block_identity": "EXCLUDED",
            "raw_session_relative_sequences": True,
            "summary_features": [
                "mean", "std", "min", "max", "p50", "p90", "p95", "p99",
                "late_count_at_1.5x_within_sequence_mean", "longest_late_run",
                "lag1_autocorrelation", "low_frequency_energy", "total_session_span",
            ],
            "outlier_trimming": "PROHIBITED",
            "winsorization": "PROHIBITED",
        },
        "feature_raw_widths": raw_widths(),
        "session_conditioning": "conditioned on public session existence; within-session relative timestamps only",
        "positive_control_path": "pinned native framework, direct unshaped action observations, real authenticated descriptor resolution only, no fixed dummy schedule",
        "liveness_cap_ms": 60000,
        "timing_confirmatory_sessions": 0,
        "final_holdout_construction": False,
    }
    freeze_path = ROOT / "V12_TIMING_ATTACK_DEVELOPMENT_PROTOCOL_FREEZE.json"
    write_json(freeze_path, protocol)
    write_json(
        ROOT / "V12_TIMING_V3_PROFILE_CANDIDATES_FREEZE.json",
        {
            "schema": "AgentTool.V12TimingV3ProfileCandidateFreeze/1",
            "protocol_sha256": sha(freeze_path),
            "profiles": profiles,
            "candidate_set_frozen_before_sessions": True,
        },
    )
    write_json(
        ROOT / "V12_TIMING_V3_FUNCTIONAL_CAPACITY_MANIFEST.json",
        {
            "schema": "AgentTool.V12TimingV3FunctionalCapacityManifest/1",
            "protocol_sha256": sha(freeze_path),
            "p10_prior_capacity_reuse": "INVALIDATED_BY_V3_PROFILE_AND_RUNNER_BINDING_CHANGE",
            "candidates": [
                {"delta_ms": delta, "workloads": functional_workloads(delta)}
                for delta in (10, 20, 25)
            ],
            "forbidden_identity_prefixes": ["DEV-TD-", "DEV-TPCIC-", "DEV-MDCC-", "DEV-CHR-"],
            "retry": "PROHIBITED",
            "replacement": "PROHIBITED",
        },
    )


if __name__ == "__main__":
    main()
