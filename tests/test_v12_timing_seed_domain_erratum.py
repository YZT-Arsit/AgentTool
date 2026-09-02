from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from v12_timing.classifier import (
    MODEL_NAMES,
    SKLEARN_RANDOM_STATE_MODULUS,
    deterministic_train_cv_folds,
    frozen_model_protocol,
    frozen_models,
    sklearn_random_state,
)
from v12_timing.projection import timing_feature_vector
from v12_timing.sentinel_v3 import select_complete_blocks

ROOT = Path(__file__).resolve().parents[1]
FAILED_RAW_FOLD_SEED = 14552047685264201170


def _manifest() -> dict[str, object]:
    return json.loads(
        (ROOT / "V12_P10_TIMING_SENTINEL_V3_FREEZE.json").read_text(encoding="utf-8")
    )


def _estimator_random_state(model: object) -> int:
    if hasattr(model, "named_steps"):
        final = list(model.named_steps.values())[-1]
    else:
        final = model
    return int(final.get_params()["random_state"])


def test_failed_uint64_seed_maps_into_sklearn_domain() -> None:
    mapped = sklearn_random_state(FAILED_RAW_FOLD_SEED)
    assert mapped == FAILED_RAW_FOLD_SEED % SKLEARN_RANDOM_STATE_MODULUS
    assert 0 <= mapped <= 2**32 - 1
    with pytest.raises(ValueError, match="nonnegative"):
        sklearn_random_state(-1)


def test_all_frozen_coordinate_and_model_fold_seeds_construct_estimators() -> None:
    for coordinate in _manifest()["physical_coordinates"]:
        for observer_index, _observer in enumerate(coordinate["observers"]):
            raw_coordinate_seed = int(coordinate["analysis_seed"]) + observer_index
            final_models = frozen_models(raw_coordinate_seed)
            assert tuple(final_models) == MODEL_NAMES
            assert all(
                0 <= _estimator_random_state(model) <= 2**32 - 1
                for model in final_models.values()
            )
            for model_index, name in enumerate(MODEL_NAMES):
                for fold_index in range(5):
                    raw_fold_seed = (
                        raw_coordinate_seed + 10_000 * (model_index + 1) + fold_index
                    )
                    model = frozen_models(raw_fold_seed)[name]
                    assert _estimator_random_state(model) == sklearn_random_state(
                        raw_fold_seed
                    )


def test_raw_uint64_seed_still_controls_train_cv_ordering() -> None:
    blocks = tuple(range(180))
    raw = FAILED_RAW_FOLD_SEED - 10_000
    assert deterministic_train_cv_folds(
        blocks, seed=raw
    ) == deterministic_train_cv_folds(blocks, seed=raw)
    assert deterministic_train_cv_folds(
        blocks, seed=raw
    ) != deterministic_train_cv_folds(blocks, seed=sklearn_random_state(raw))


def test_normalization_does_not_change_selected_blocks() -> None:
    manifest = _manifest()
    statuses = {identity: "COMPLETE" for identity in manifest["identity_manifest"]}
    before = select_complete_blocks(manifest, statuses)
    for coordinate in manifest["physical_coordinates"]:
        frozen_models(int(coordinate["analysis_seed"]))
    after = select_complete_blocks(manifest, statuses)
    assert before == after


def test_normalization_does_not_change_feature_vectors() -> None:
    projection = {
        "observer": "REGISTRY",
        "view": "TIMING_ONLY_VIEW",
        "session_relative_query_arrival_ns": [0.0, 2.0, 5.0],
        "inter_query_gap_ns": [2.0, 3.0],
        "session_relative_response_send_ns": [1.0, 4.0, 8.0],
        "query_response_ns": [1.0, 2.0, 3.0],
        "total_resolution_session_span_ns": 8.0,
    }
    before = timing_feature_vector(projection, raw_widths=(3, 2, 3, 3))
    frozen_models(FAILED_RAW_FOLD_SEED)
    after = timing_feature_vector(projection, raw_widths=(3, 2, 3, 3))
    assert before == after


def test_only_random_state_representation_changes_model_parameters() -> None:
    raw_seed = FAILED_RAW_FOLD_SEED
    mapped = sklearn_random_state(raw_seed)
    models = frozen_models(raw_seed)
    protocol = frozen_model_protocol()
    for name, model in models.items():
        assert _estimator_random_state(model) == mapped
        params = (
            list(model.named_steps.values())[-1].get_params()
            if hasattr(model, "named_steps")
            else model.get_params()
        )
        for parameter, expected in protocol[name]["hyperparameters"].items():
            assert params[parameter] == expected


def test_all_frozen_families_fit_synthetic_timing_shaped_fixture() -> None:
    rng = np.random.default_rng(91)
    labels = np.tile(np.asarray([0, 1], dtype=np.int64), 20)
    vectors = rng.normal(size=(40, 17))
    vectors[:, 0] += labels * 0.25
    for model in frozen_models(FAILED_RAW_FOLD_SEED).values():
        model.fit(vectors, labels)
        probabilities = model.predict_proba(vectors)
        assert probabilities.shape == (40, 2)
        assert np.all(np.isfinite(probabilities))
