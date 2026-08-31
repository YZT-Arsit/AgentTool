from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from sklearn.base import ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .statistics import BlockSplit, partition_indices, validate_matched_blocks

MODEL_NAMES = ("LOGISTIC_REGRESSION", "EXTRA_TREES", "HIST_GRADIENT_BOOSTING", "RBF_SVM")


def frozen_models(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "LOGISTIC_REGRESSION": make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2_000, random_state=seed)),
        "EXTRA_TREES": ExtraTreesClassifier(n_estimators=300, min_samples_leaf=3, max_features="sqrt", n_jobs=1, random_state=seed),
        "HIST_GRADIENT_BOOSTING": HistGradientBoostingClassifier(learning_rate=0.08, max_iter=200, max_leaf_nodes=15, l2_regularization=1.0, random_state=seed),
        "RBF_SVM": make_pipeline(StandardScaler(), SVC(C=1.0, gamma="scale", kernel="rbf", probability=True, random_state=seed)),
    }


@dataclass(frozen=True)
class FrozenTrainEvalPredictions:
    eval_labels: np.ndarray
    eval_blocks: np.ndarray
    predictions: Mapping[str, np.ndarray]
    train_sample_count: int
    eval_sample_count: int


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
