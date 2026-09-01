from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np

from .profile import delta_functional_candidate_profiles
from .statistics import BOOTSTRAP_RESAMPLES, matched_block_bootstrap_auc_values


BASE_EVAL_BLOCK_CANDIDATES = (150, 200, 250, 300, 400, 500)
EXTENDED_EVAL_BLOCK_CANDIDATES = (600, 750, 1000)
NULL_TRUE_AUC = 0.5
PROTECTED_UCB_LIMIT = 0.55
PLANNING_SUCCESS_PROBABILITY = 0.90
TRAIN_FRACTION = 0.60
EVAL_FRACTION = 0.40
FUTURE_WORKLOAD_COMPARISONS = (
    "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10",
    "C1_REGISTRY_RESOLUTION_PATTERN",
)
FUTURE_FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


def _quantile(values: np.ndarray, probability: float) -> float:
    return float(np.quantile(values, probability))


def _trial_seed(seed: int, eval_blocks: int, trial: int, purpose: str) -> int:
    digest = hashlib.sha256(f"{seed}|N{eval_blocks}|T{trial}|{purpose}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def calibrate_null_candidate(
    eval_blocks: int,
    *,
    trials: int,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int,
) -> dict[str, float | int]:
    """Simulate numeric fixed-score arrays only; no trace or projection input exists."""

    if eval_blocks < 2 or trials < 1 or bootstrap_resamples < 1:
        raise ValueError("null planning dimensions must be positive")
    labels = np.tile(np.asarray([0, 1], dtype=np.int64), eval_blocks)
    blocks = np.repeat(np.arange(eval_blocks, dtype=np.int64), 2)
    upper_bounds = np.empty(trials, dtype=np.float64)
    for trial in range(trials):
        score_rng = np.random.default_rng(_trial_seed(seed, eval_blocks, trial, "SCORES"))
        bootstrap_rng = np.random.default_rng(_trial_seed(seed, eval_blocks, trial, "BOOTSTRAP"))
        scores = score_rng.standard_normal(2 * eval_blocks)
        bootstrap = matched_block_bootstrap_auc_values(
            labels,
            scores,
            blocks,
            generator=bootstrap_rng,
            resamples=bootstrap_resamples,
        )
        upper_bounds[trial] = np.quantile(bootstrap, 0.95)
    probability = float(np.mean(upper_bounds <= PROTECTED_UCB_LIMIT))
    return {
        "eval_blocks": int(eval_blocks),
        "outer_null_trials": int(trials),
        "bootstrap_resamples_per_trial": int(bootstrap_resamples),
        "median_ucb95": _quantile(upper_bounds, 0.50),
        "p90_ucb95": _quantile(upper_bounds, 0.90),
        "p95_ucb95": _quantile(upper_bounds, 0.95),
        "probability_ucb95_le_0_55": probability,
        "planning_criterion_pass": probability >= PLANNING_SUCCESS_PROBABILITY,
    }


def derive_block_denominator(eval_blocks: int) -> dict[str, int | float]:
    total = eval_blocks / EVAL_FRACTION
    if not total.is_integer():
        raise ValueError("selected EVAL denominator cannot realize an exact 60/40 block split")
    total_blocks = int(total)
    train_blocks = total_blocks - eval_blocks
    if train_blocks / total_blocks != TRAIN_FRACTION:
        raise AssertionError("derived TRAIN denominator is not exactly 60 percent")
    return {
        "total_blocks_per_coordinate": total_blocks,
        "train_blocks": train_blocks,
        "eval_blocks": int(eval_blocks),
        "sessions_per_coordinate": 2 * total_blocks,
    }


def protected_execution_cost(eval_blocks: int) -> dict[str, object]:
    denominator = derive_block_denominator(eval_blocks)
    comparisons = len(FUTURE_WORKLOAD_COMPARISONS)
    frameworks = len(FUTURE_FRAMEWORKS)
    coordinates_per_profile = comparisons * frameworks
    sessions_per_profile = denominator["sessions_per_coordinate"] * coordinates_per_profile
    profile_rows = []
    all_sessions = 0
    all_floor_ms = 0
    for profile in delta_functional_candidate_profiles():
        per_session_floor_ms = max(profile.scheduled_lifetime_ms, profile.pir_public_epoch_ms)
        serial_floor_ms = sessions_per_profile * per_session_floor_ms
        all_sessions += sessions_per_profile
        all_floor_ms += serial_floor_ms
        profile_rows.append({
            "profile_id": profile.profile_id,
            "delta_ms": profile.round_period_ms,
            "workload_coordinates": coordinates_per_profile,
            "sessions": sessions_per_profile,
            "public_schedule_floor_ms_per_session": per_session_floor_ms,
            "serial_public_schedule_floor_ms": serial_floor_ms,
            "serial_public_schedule_floor_hours": serial_floor_ms / 3_600_000,
        })
    return {
        **denominator,
        "workload_comparisons_per_framework": comparisons,
        "frameworks": frameworks,
        "observer_projection_session_reuse": True,
        "coordinates_per_profile": coordinates_per_profile,
        "profiles": profile_rows,
        "all_three_profile_sessions_worst_case": all_sessions,
        "all_three_profile_serial_public_schedule_floor_ms": all_floor_ms,
        "all_three_profile_serial_public_schedule_floor_hours": all_floor_ms / 3_600_000,
        "all_three_profile_serial_public_schedule_floor_days": all_floor_ms / 86_400_000,
        "cost_scope": "PUBLIC_SCHEDULE_FLOOR_ONLY_EXCLUDES_STARTUP_ANALYSIS_AND_QUEUEING",
    }


def run_null_precision_plan(
    *,
    trials: int,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int,
    base_candidates: Iterable[int] = BASE_EVAL_BLOCK_CANDIDATES,
    extended_candidates: Iterable[int] = EXTENDED_EVAL_BLOCK_CANDIDATES,
) -> dict[str, object]:
    results = [
        calibrate_null_candidate(
            count, trials=trials, bootstrap_resamples=bootstrap_resamples, seed=seed
        )
        for count in base_candidates
    ]
    passing = [row for row in results if row["planning_criterion_pass"]]
    extended = False
    if not passing:
        extended = True
        results.extend(
            calibrate_null_candidate(
                count, trials=trials, bootstrap_resamples=bootstrap_resamples, seed=seed
            )
            for count in extended_candidates
        )
        passing = [row for row in results if row["planning_criterion_pass"]]
    if not passing:
        raise RuntimeError("no candidate denominator satisfies the frozen null-precision criterion")
    selected = min(int(row["eval_blocks"]) for row in passing)
    return {
        "schema": "AgentTool.V12TimingNullPrecisionCalibration/1",
        "input_kind": "ARTIFICIAL_NUMERIC_SCORE_ARRAYS_ONLY",
        "reads_project_traces": False,
        "true_auc": NULL_TRUE_AUC,
        "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
        "bootstrap_resamples": int(bootstrap_resamples),
        "one_sided_ucb_percentile": 95,
        "protected_ucb_limit": PROTECTED_UCB_LIMIT,
        "required_probability": PLANNING_SUCCESS_PROBABILITY,
        "outer_null_trials": int(trials),
        "seed": int(seed),
        "extended_beyond_500": extended,
        "results": results,
        "selected_eval_blocks": selected,
        "denominator": derive_block_denominator(selected),
        "protected_execution_cost": protected_execution_cost(selected),
    }
