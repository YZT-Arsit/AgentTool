from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.base import ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .statistics import BlockSplit, distinguishability_auc, partition_indices, validate_matched_blocks

MODEL_NAMES = ("LOGISTIC_REGRESSION", "EXTRA_TREES", "HIST_GRADIENT_BOOSTING", "RBF_SVM")
MODEL_TIE_BREAK_ORDER = MODEL_NAMES
DEVELOPMENT_PROTOCOL_SEED_LABEL = "V12-TIMING-TRAIN-SELECTED-V2-20260831"


def coordinate_protocol_seed(profile: str, task: str, framework: str, observer: str) -> int:
    material = "|".join(
        (DEVELOPMENT_PROTOCOL_SEED_LABEL, profile, task, framework, observer)
    )
    return int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")


def frozen_models(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "LOGISTIC_REGRESSION": make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2_000, random_state=seed)),
        "EXTRA_TREES": ExtraTreesClassifier(n_estimators=300, min_samples_leaf=3, max_features="sqrt", n_jobs=1, random_state=seed),
        "HIST_GRADIENT_BOOSTING": HistGradientBoostingClassifier(learning_rate=0.08, max_iter=200, max_leaf_nodes=15, l2_regularization=1.0, random_state=seed),
        "RBF_SVM": make_pipeline(StandardScaler(), SVC(C=1.0, gamma="scale", kernel="rbf", probability=True, random_state=seed)),
    }


def frozen_model_protocol() -> dict[str, dict[str, Any]]:
    return {
        "LOGISTIC_REGRESSION": {
            "preprocessing": "StandardScaler fitted on the applicable TRAIN fold/all TRAIN only",
            "hyperparameters": {"C": 1.0, "max_iter": 2_000},
        },
        "EXTRA_TREES": {
            "preprocessing": "NONE",
            "hyperparameters": {"n_estimators": 300, "min_samples_leaf": 3, "max_features": "sqrt", "n_jobs": 1},
        },
        "HIST_GRADIENT_BOOSTING": {
            "preprocessing": "NONE",
            "hyperparameters": {"learning_rate": 0.08, "max_iter": 200, "max_leaf_nodes": 15, "l2_regularization": 1.0},
        },
        "RBF_SVM": {
            "preprocessing": "StandardScaler fitted on the applicable TRAIN fold/all TRAIN only",
            "hyperparameters": {"C": 1.0, "gamma": "scale", "kernel": "rbf", "probability": True},
        },
    }


@dataclass(frozen=True)
class FrozenTrainEvalPredictions:
    eval_labels: np.ndarray
    eval_blocks: np.ndarray
    predictions: Mapping[str, np.ndarray]
    train_sample_count: int
    eval_sample_count: int


@dataclass(frozen=True)
class TrainModelDiagnostic:
    raw_train_cv_auc: float
    orientation: str
    train_distinguishability_auc: float


@dataclass(frozen=True)
class TrainSelectedEvalPredictions:
    selected_model: str
    orientation: str
    train_diagnostics: Mapping[str, TrainModelDiagnostic]
    eval_labels: np.ndarray
    eval_blocks: np.ndarray
    oriented_eval_scores: np.ndarray
    train_block_count: int
    eval_block_count: int
    train_sample_count: int
    eval_sample_count: int
    decisive_eval_model_count: int = 1


def deterministic_train_cv_folds(
    train_blocks: Sequence[int], *, seed: int, folds: int = 5
) -> tuple[tuple[int, ...], ...]:
    unique = sorted(set(int(value) for value in train_blocks))
    if folds < 2 or len(unique) < folds:
        raise ValueError("TRAIN-only model selection requires at least one complete block per CV fold")
    ordered = sorted(
        unique,
        key=lambda block: hashlib.sha256(f"{seed}|TRAIN-CV|B{block}".encode()).digest(),
    )
    output = tuple(tuple(sorted(ordered[index::folds])) for index in range(folds))
    if any(not fold for fold in output) or set().union(*map(set, output)) != set(unique):
        raise AssertionError("TRAIN CV fold construction lost a complete block")
    return output


def _positive_scores(model: ClassifierMixin, values: np.ndarray) -> np.ndarray:
    probabilities = np.asarray(model.predict_proba(values), dtype=np.float64)
    if probabilities.shape != (len(values), 2):
        raise ValueError("frozen binary classifier did not return two-class probabilities")
    return probabilities[:, 1]


def select_on_train_fit_predict_eval(
    vectors: Sequence[Sequence[float]],
    labels: Sequence[int],
    blocks: Sequence[int],
    split: BlockSplit,
    *,
    seed: int,
    cv_folds: int = 5,
) -> TrainSelectedEvalPredictions:
    """Select one model and score orientation without consulting EVAL."""

    matrix = np.asarray(vectors, dtype=np.float64)
    target = np.asarray(labels, dtype=np.int64)
    groups = np.asarray(blocks, dtype=np.int64)
    if matrix.ndim != 2 or len(matrix) != len(target) or len(target) != len(groups):
        raise ValueError("feature matrix, labels, and blocks must align")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("feature matrix must be finite")
    validate_matched_blocks(target, groups)
    train, evaluation = partition_indices(groups, split)
    train_groups = groups[train]
    folds = deterministic_train_cv_folds(train_groups, seed=seed, folds=cv_folds)
    diagnostics: dict[str, TrainModelDiagnostic] = {}
    for model_index, name in enumerate(MODEL_NAMES):
        out_of_fold = np.full(len(train), np.nan, dtype=np.float64)
        for fold_index, held_out_blocks in enumerate(folds):
            held_out = np.isin(train_groups, held_out_blocks)
            fitting = ~held_out
            if not np.any(fitting) or not np.any(held_out):
                raise AssertionError("TRAIN CV fold is empty")
            fold_seed = seed + 10_000 * (model_index + 1) + fold_index
            model = frozen_models(fold_seed)[name]
            model.fit(matrix[train[fitting]], target[train[fitting]])
            out_of_fold[held_out] = _positive_scores(model, matrix[train[held_out]])
        if np.any(~np.isfinite(out_of_fold)):
            raise AssertionError("TRAIN CV did not score every TRAIN session exactly once")
        raw_auc = float(roc_auc_score(target[train], out_of_fold))
        orientation = "NORMAL" if raw_auc >= 0.5 else "INVERTED"
        diagnostics[name] = TrainModelDiagnostic(
            raw_train_cv_auc=raw_auc,
            orientation=orientation,
            train_distinguishability_auc=distinguishability_auc(raw_auc),
        )
    selected = max(
        MODEL_TIE_BREAK_ORDER,
        key=lambda name: (
            diagnostics[name].train_distinguishability_auc,
            -MODEL_TIE_BREAK_ORDER.index(name),
        ),
    )
    final_model = frozen_models(seed)[selected]
    final_model.fit(matrix[train], target[train])
    raw_eval = _positive_scores(final_model, matrix[evaluation])
    orientation = diagnostics[selected].orientation
    oriented_eval = raw_eval if orientation == "NORMAL" else 1.0 - raw_eval
    return TrainSelectedEvalPredictions(
        selected_model=selected,
        orientation=orientation,
        train_diagnostics=diagnostics,
        eval_labels=target[evaluation].copy(),
        eval_blocks=groups[evaluation].copy(),
        oriented_eval_scores=oriented_eval,
        train_block_count=len(split.train_blocks),
        eval_block_count=len(split.eval_blocks),
        train_sample_count=len(train),
        eval_sample_count=len(evaluation),
    )


def fit_train_predict_eval(vectors: Sequence[Sequence[float]], labels: Sequence[int], blocks: Sequence[int],
                           split: BlockSplit, *, seed: int) -> FrozenTrainEvalPredictions:
    matrix = np.asarray(vectors, dtype=np.float64)
    target = np.asarray(labels, dtype=np.int64)
    groups = np.asarray(blocks, dtype=np.int64)
    if matrix.ndim != 2 or len(matrix) != len(target) or len(target) != len(groups):
        raise ValueError("feature matrix, labels, and blocks must align")
    validate_matched_blocks(target, groups)
    train, evaluation = partition_indices(groups, split)
    output: dict[str, np.ndarray] = {}
    for name, model in frozen_models(seed).items():
        model.fit(matrix[train], target[train])
        output[name] = model.predict_proba(matrix[evaluation])[:, 1]
    return FrozenTrainEvalPredictions(target[evaluation].copy(), groups[evaluation].copy(), output,
                                      len(train), len(evaluation))
