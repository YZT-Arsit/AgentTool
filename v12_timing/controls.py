from __future__ import annotations

from dataclasses import asdict
from typing import Sequence

import numpy as np

from .classifier import select_on_train_fit_predict_eval
from .profile import TimingIndistinguishabilityProfile, delta_functional_candidate_profiles
from .projection import (
    TIMING_ONLY_VIEW,
    expected_raw_timing_widths,
    registry_timing_projection,
    relay_timing_projection,
    timing_feature_vector,
)
from .statistics import (
    BOOTSTRAP_RESAMPLES,
    bootstrap_selected_model_auc,
    deterministic_block_split,
    paired_auc_randomization_test,
)


SYNTHETIC_CONTROL_PROFILE_DELTA_MS = 25
SYNTHETIC_CONTROL_TOTAL_BLOCKS = 250
SYNTHETIC_CONTROL_TRAIN_BLOCKS = 150
SYNTHETIC_CONTROL_EVAL_BLOCKS = 100
SYNTHETIC_CONTROL_LCB_LIMIT = 0.60
SYNTHETIC_RESPONSE_SHIFT_NS = 3_000_000


def _profile() -> TimingIndistinguishabilityProfile:
    return next(
        profile
        for profile in delta_functional_candidate_profiles()
        if profile.round_period_ms == SYNTHETIC_CONTROL_PROFILE_DELTA_MS
    )


def _positive_ints(values: np.ndarray) -> np.ndarray:
    return np.maximum(1, np.rint(values).astype(np.int64))


def _relay_projection(
    profile: TimingIndistinguishabilityProfile,
    *,
    block: int,
    label: int,
    generator: np.random.Generator,
) -> dict[str, object]:
    count = profile.total_rounds
    gaps = _positive_ints(
        generator.normal(profile.round_period_ms * 1_000_000, 120_000, size=count - 1)
    )
    arrivals = np.concatenate((np.asarray([0], dtype=np.int64), np.cumsum(gaps)))
    origin = 10_000_000_000_000 + block * 100_000_000_000
    arrivals += origin
    base_latency = _positive_ints(generator.normal(1_500_000, 70_000, size=count))
    pattern = ((np.arange(count) % 11) < 3).astype(np.int64) * 450_000
    latencies = base_latency + label * (SYNTHETIC_RESPONSE_SHIFT_NS + pattern)
    sends = arrivals + latencies
    rows = [
        {
            "profile_id": profile.profile_id,
            "session": 1,
            "round": index + 1,
            "request_length": profile.request_final_bytes,
            "response_length": profile.response_final_bytes,
            "request_observed_ns": int(arrivals[index]),
            "response_send_ns": int(sends[index]),
        }
        for index in range(count)
    ]
    projection = relay_timing_projection(
        {"public_relay_events": rows},
        expected_rounds=count,
        require_complete_application_timing=True,
    )
    if projection["view"] != TIMING_ONLY_VIEW:
        raise AssertionError("synthetic Relay control did not produce complete application timing")
    return projection


def _registry_projection(
    profile: TimingIndistinguishabilityProfile,
    *,
    block: int,
    label: int,
    generator: np.random.Generator,
) -> dict[str, object]:
    count = profile.pir_resolution_opportunities
    gaps = _positive_ints(
        generator.normal(profile.pir_resolution_period_ms * 1_000_000, 140_000, size=count - 1)
    )
    arrivals = np.concatenate((np.asarray([0], dtype=np.int64), np.cumsum(gaps)))
    origin = 20_000_000_000_000 + block * 100_000_000_000
    arrivals += origin
    base_latency = _positive_ints(generator.normal(2_000_000, 80_000, size=count))
    pattern = ((np.arange(count) % 9) == 0).astype(np.int64) * 600_000
    sends = arrivals + base_latency + label * (SYNTHETIC_RESPONSE_SHIFT_NS + pattern)
    rows = [
        {
            "ordinal": index,
            "query_bytes": 2020,
            "answer_bytes": 6592,
            "query_rows": 501,
            "query_cols": 1,
            "request_arrival_ns": int(arrivals[index]),
            "response_send_ns": int(sends[index]),
        }
        for index in range(count)
    ]
    projection = registry_timing_projection(
        rows,
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=count,
        require_complete_application_timing=True,
    )
    if projection["view"] != TIMING_ONLY_VIEW:
        raise AssertionError("synthetic Registry control did not produce complete application timing")
    return projection


def synthetic_timing_control_dataset(
    observer: str,
    *,
    total_blocks: int = SYNTHETIC_CONTROL_TOTAL_BLOCKS,
    seed: int,
) -> tuple[list[list[float]], list[int], list[int], tuple[int, ...]]:
    if observer not in {"RELAY", "REGISTRY"}:
        raise ValueError("synthetic control observer must be RELAY or REGISTRY")
    if total_blocks < 5:
        raise ValueError("synthetic control needs at least five complete blocks")
    profile = _profile()
    widths = expected_raw_timing_widths(
        observer,
        public_r=profile.total_rounds,
        public_q=profile.pir_resolution_opportunities,
        has_relay_send=observer == "RELAY",
        has_registry_send=observer == "REGISTRY",
    )
    vectors: list[list[float]] = []
    labels: list[int] = []
    blocks: list[int] = []
    for block in range(total_blocks):
        shared_seed = int.from_bytes(
            np.random.SeedSequence([seed, block]).generate_state(2).tobytes(), "little"
        )
        for label in (0, 1):
            # Identical seed within a matched block keeps baseline jitter fixed;
            # only the predeclared response timing pattern changes.
            generator = np.random.default_rng(shared_seed)
            projection = (
                _relay_projection(profile, block=block, label=label, generator=generator)
                if observer == "RELAY"
                else _registry_projection(profile, block=block, label=label, generator=generator)
            )
            vector = timing_feature_vector(projection, raw_widths=widths)
            vectors.append(vector)
            labels.append(label)
            blocks.append(block)
    if len({len(vector) for vector in vectors}) != 1:
        raise AssertionError("synthetic timing control vector width changed by class")
    return vectors, labels, blocks, widths


def run_synthetic_timing_pipeline_control(
    observer: str,
    *,
    seed: int,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    randomization_resamples: int = 2_000,
) -> dict[str, object]:
    vectors, labels, blocks, widths = synthetic_timing_control_dataset(observer, seed=seed)
    split = deterministic_block_split(blocks, seed_hex=f"SYNTHETIC-CONTROL-{seed}")
    if (len(split.train_blocks), len(split.eval_blocks)) != (
        SYNTHETIC_CONTROL_TRAIN_BLOCKS,
        SYNTHETIC_CONTROL_EVAL_BLOCKS,
    ):
        raise AssertionError("synthetic control did not preserve its frozen 60/40 block split")
    selected = select_on_train_fit_predict_eval(
        vectors, labels, blocks, split, seed=seed, cv_folds=5
    )
    inference = bootstrap_selected_model_auc(
        selected.eval_labels,
        selected.oriented_eval_scores,
        selected.eval_blocks,
        seed=seed + 1,
        resamples=bootstrap_resamples,
    )
    randomization = paired_auc_randomization_test(
        selected.eval_labels,
        selected.oriented_eval_scores,
        selected.eval_blocks,
        seed=seed + 2,
        resamples=randomization_resamples,
    )
    passed = float(inference["auc_lcb95_one_sided"]) >= SYNTHETIC_CONTROL_LCB_LIMIT
    return {
        "schema": "AgentTool.V12SyntheticTimingPipelineControl/1",
        "observer": observer,
        "profile_id": _profile().profile_id,
        "artificial_numeric_timing_only": True,
        "reads_project_traces": False,
        "fixed_public_R": _profile().total_rounds,
        "fixed_public_Q": _profile().pir_resolution_opportunities,
        "fixed_raw_sequence_widths": list(widths),
        "feature_vector_width": len(vectors[0]),
        "total_blocks": SYNTHETIC_CONTROL_TOTAL_BLOCKS,
        "train_blocks": selected.train_block_count,
        "eval_blocks": selected.eval_block_count,
        "class_members_per_block": 2,
        "response_shift_ns": SYNTHETIC_RESPONSE_SHIFT_NS,
        "selected_model": selected.selected_model,
        "train_frozen_orientation": selected.orientation,
        "train_diagnostics": {
            name: asdict(diagnostic) for name, diagnostic in selected.train_diagnostics.items()
        },
        "decisive_eval_model_count": selected.decisive_eval_model_count,
        "inference": inference,
        "randomization": randomization,
        "control_lcb_rule": "AUC_LCB95 >= 0.60",
        "status": "PASS" if passed else "FAIL",
        "protected_trace_sessions_read": 0,
        "protected_classifier_training_runs": 0,
        "protected_real_auc_calculations": 0,
    }


def run_all_synthetic_timing_pipeline_controls(
    *, seed: int, bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
) -> dict[str, object]:
    results = [
        run_synthetic_timing_pipeline_control(
            observer,
            seed=seed + index * 100,
            bootstrap_resamples=bootstrap_resamples,
        )
        for index, observer in enumerate(("RELAY", "REGISTRY"))
    ]
    return {
        "schema": "AgentTool.V12SyntheticTimingPipelineControlClosure/1",
        "results": results,
        "status": "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL",
        "protected_trace_sessions_read": 0,
        "protected_classifier_training_runs": 0,
        "protected_real_auc_calculations": 0,
    }
