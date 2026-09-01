from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from v12_timing import classifier
from v12_timing.classifier import coordinate_protocol_seed, select_on_train_fit_predict_eval
from v12_timing.controls import synthetic_timing_control_dataset
from v12_timing.matched_tasks import (
    AUXILIARY_REGISTRY_COMPOSITE,
    PRIMARY_COMPOSITE_TASKS,
    PRIMARY_ISOLATED_TASKS,
    SENTINEL_COMPARISONS,
    timing_task_protocol_manifest,
)
from v12_timing.planning import derive_block_denominator, protected_execution_cost
from v12_timing.statistics import (
    BlockSplit,
    bootstrap_selected_model_auc,
    matched_block_bootstrap_auc_values,
    paired_auc_randomization_test,
    validate_matched_blocks,
)


ROOT = Path(__file__).resolve().parents[1]


class _RecordingModel:
    def __init__(self, name: str, calls: list[tuple[str, str, np.ndarray]]) -> None:
        self.name = name
        self.calls = calls

    def fit(self, values: np.ndarray, labels: np.ndarray) -> "_RecordingModel":
        self.calls.append((self.name, "fit", values.copy()))
        return self

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        self.calls.append((self.name, "predict", values.copy()))
        if self.name == "LOGISTIC_REGRESSION":
            positive = values[:, 1]
        elif self.name == "EXTRA_TREES":
            positive = 1.0 - values[:, 1]
        else:
            positive = np.full(len(values), 0.5)
        return np.column_stack((1.0 - positive, positive))


def _fixed_split_data() -> tuple[np.ndarray, np.ndarray, np.ndarray, BlockSplit]:
    blocks = np.repeat(np.arange(10, dtype=np.int64), 2)
    labels = np.tile(np.asarray([0, 1], dtype=np.int64), 10)
    vectors = np.column_stack((blocks, labels, np.linspace(0.0, 1.0, len(labels))))
    split = BlockSplit(tuple(range(6)), tuple(range(6, 10))).validate()
    return vectors, labels, blocks, split


def test_train_only_selection_never_fits_on_or_selects_with_eval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, np.ndarray]] = []
    monkeypatch.setattr(
        classifier,
        "frozen_models",
        lambda seed: {
            name: _RecordingModel(name, calls) for name in classifier.MODEL_NAMES
        },
    )
    vectors, labels, blocks, split = _fixed_split_data()
    first = select_on_train_fit_predict_eval(
        vectors, labels, blocks, split, seed=17, cv_folds=3
    )
    changed_eval = vectors.copy()
    changed_eval[blocks >= 6, 2] += 10_000.0
    second = select_on_train_fit_predict_eval(
        changed_eval, labels, blocks, split, seed=17, cv_folds=3
    )

    assert first.selected_model == second.selected_model == "LOGISTIC_REGRESSION"
    assert first.orientation == second.orientation == "NORMAL"
    assert first.train_diagnostics == second.train_diagnostics
    assert first.decisive_eval_model_count == second.decisive_eval_model_count == 1
    assert all(np.max(values[:, 0]) <= 5 for _, operation, values in calls if operation == "fit")
    eval_predictors = {
        name
        for name, operation, values in calls
        if operation == "predict" and np.min(values[:, 0]) >= 6
    }
    assert eval_predictors == {"LOGISTIC_REGRESSION"}


def test_train_frozen_inverted_orientation_is_applied_before_eval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, np.ndarray]] = []

    class InvertedLogistic(_RecordingModel):
        def predict_proba(self, values: np.ndarray) -> np.ndarray:
            self.calls.append((self.name, "predict", values.copy()))
            positive = 1.0 - values[:, 1] if self.name == "LOGISTIC_REGRESSION" else np.full(len(values), 0.5)
            return np.column_stack((1.0 - positive, positive))

    monkeypatch.setattr(
        classifier,
        "frozen_models",
        lambda seed: {
            name: InvertedLogistic(name, calls) for name in classifier.MODEL_NAMES
        },
    )
    vectors, labels, blocks, split = _fixed_split_data()
    result = select_on_train_fit_predict_eval(
        vectors, labels, blocks, split, seed=19, cv_folds=3
    )
    assert result.selected_model == "LOGISTIC_REGRESSION"
    assert result.orientation == "INVERTED"
    assert np.array_equal(result.oriented_eval_scores, result.eval_labels.astype(float))


def test_selected_eval_auc_is_not_post_hoc_reoriented() -> None:
    labels = np.tile(np.asarray([0, 1]), 4)
    blocks = np.repeat(np.arange(4), 2)
    normal = bootstrap_selected_model_auc(labels, labels.astype(float), blocks, seed=1, resamples=50)
    reversed_result = bootstrap_selected_model_auc(
        labels, 1.0 - labels.astype(float), blocks, seed=1, resamples=50
    )
    assert normal["selected_model_eval_auc"] == 1.0
    assert reversed_result["selected_model_eval_auc"] == 0.0
    assert reversed_result["auc_ucb95_one_sided"] == 0.0
    assert reversed_result["post_hoc_eval_orientation"] is False


def test_vectorized_bootstrap_resamples_whole_blocks_and_preserves_multiplicity() -> None:
    labels = np.tile(np.asarray([0, 1]), 3)
    blocks = np.repeat(np.arange(3), 2)
    scores = np.asarray([0.1, 0.9, 0.8, 0.2, 0.4, 0.6])
    values = matched_block_bootstrap_auc_values(
        labels,
        scores,
        blocks,
        generator=np.random.default_rng(5),
        resamples=200,
        chunk_size=17,
    )
    assert len(values) == 200
    assert np.all((0.0 <= values) & (values <= 1.0))
    perfect = matched_block_bootstrap_auc_values(
        labels,
        labels.astype(float),
        blocks,
        generator=np.random.default_rng(6),
        resamples=25,
    )
    assert np.array_equal(perfect, np.ones(25))

    multiplicities = np.asarray([[3, 0, 0], [0, 2, 1], [1, 1, 1]], dtype=np.int64)

    class FixedMultinomial:
        def multinomial(self, count: int, probabilities: np.ndarray, size: int) -> np.ndarray:
            assert count == 3 and size == 3
            return multiplicities.copy()

    exact = matched_block_bootstrap_auc_values(
        labels,
        scores,
        blocks,
        generator=FixedMultinomial(),  # type: ignore[arg-type]
        resamples=3,
        chunk_size=3,
    )
    expected = []
    for counts in multiplicities:
        indices = np.concatenate(
            [np.tile(np.asarray([2 * block, 2 * block + 1]), count) for block, count in enumerate(counts) if count]
        )
        expected.append(roc_auc_score(labels[indices], scores[indices]))
    assert exact == pytest.approx(expected)


def test_randomization_is_only_within_complete_pairs() -> None:
    labels = np.tile(np.asarray([0, 1]), 5)
    blocks = np.repeat(np.arange(5), 2)
    scores = labels.astype(float)
    result = paired_auc_randomization_test(labels, scores, blocks, seed=9, resamples=30)
    validate_matched_blocks(labels, blocks)
    assert result["randomization_unit"] == "WITHIN_COMPLETE_MATCHED_BLOCK_LABEL_SWAP"
    assert result["role"] == "SECONDARY_NULL_CONSISTENCY_DIAGNOSTIC"


def test_frozen_denominator_and_exact_public_schedule_cost() -> None:
    denominator = derive_block_denominator(600)
    assert denominator == {
        "total_blocks_per_coordinate": 1500,
        "train_blocks": 900,
        "eval_blocks": 600,
        "sessions_per_coordinate": 3000,
    }
    cost = protected_execution_cost(600)
    assert cost["coordinates_per_profile"] == 20
    assert all(row["sessions"] == 60_000 for row in cost["profiles"])
    assert cost["all_three_profile_sessions_worst_case"] == 180_000
    assert cost["all_three_profile_serial_public_schedule_floor_hours"] == 300.0


@pytest.mark.parametrize("observer", ("RELAY", "REGISTRY"))
def test_synthetic_control_has_fixed_public_event_count_and_vector_width(observer: str) -> None:
    vectors, labels, blocks, widths = synthetic_timing_control_dataset(
        observer, total_blocks=5, seed=23
    )
    assert len(vectors) == len(labels) == len(blocks) == 10
    assert len({len(vector) for vector in vectors}) == 1
    assert all(len(vector) == sum(widths) + 12 * len(widths) + 1 for vector in vectors)
    members = validate_matched_blocks(labels, blocks)
    assert len(members) == 5


def test_task_and_sentinel_protocol_freeze() -> None:
    manifest = timing_task_protocol_manifest()
    assert PRIMARY_ISOLATED_TASKS == ("T2", "T3", "T4", "T5", "T6", "T9")
    assert PRIMARY_COMPOSITE_TASKS == ("T7", "T8", "T10")
    assert SENTINEL_COMPARISONS == (AUXILIARY_REGISTRY_COMPOSITE, "T4", "T7", "T9")
    assert manifest["auxiliary_registry_composite"]["estimand"] == "COMPOSITE"
    assert manifest["auxiliary_registry_composite"]["causal_attribution"] is False


def test_development_coordinate_seed_is_deterministic_and_coordinate_specific() -> None:
    first = coordinate_protocol_seed("P10", "T2", "OpenAI", "RELAY")
    assert first == coordinate_protocol_seed("P10", "T2", "OpenAI", "RELAY")
    assert first != coordinate_protocol_seed("P10", "T2", "OpenAI", "REGISTRY")
    assert first != coordinate_protocol_seed("P20", "T2", "OpenAI", "RELAY")


def test_append_only_closure_evidence_records_zero_protected_execution() -> None:
    calibration = json.loads((ROOT / "V12_TIMING_NULL_PRECISION_CALIBRATION.json").read_text())
    controls = json.loads((ROOT / "V12_TIMING_SYNTHETIC_PIPELINE_CONTROL.json").read_text())
    closure = json.loads(
        (ROOT / "V12_TIMING_STATISTICAL_PROTOCOL_AND_LOCAL_CONTROL_CLOSURE.json").read_text()
    )
    protocol = json.loads((ROOT / "V12_TIMING_STATISTICAL_PROTOCOL_V2.json").read_text())
    assert calibration["outer_null_trials"] == 250
    assert calibration["bootstrap_resamples"] == 10_000
    assert calibration["selected_eval_blocks"] == 600
    assert controls["status"] == "PASS"
    assert all(row["reads_project_traces"] is False for row in controls["results"])
    prohibited = closure["prohibited_execution"]
    assert prohibited["protected_classifier_training_runs"] == 0
    assert prohibited["protected_real_auc_calculations"] == 0
    assert prohibited["selected_timing_delta_ms"] == "NONE"
    assert all(
        row["match"] is True for row in protocol["runtime_immutability"]["files"].values()
    )
