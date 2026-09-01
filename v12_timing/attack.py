from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.base import ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


BOOTSTRAP_RESAMPLES = 10_000
FOLDS = 5
BINARY_CHANCE = 0.50
BINARY_EQUIVALENCE_LIMIT = 0.55
POSITIVE_CONTROL_LOWER_LIMIT = 0.60


@dataclass(frozen=True)
class AttackResult:
    model: str
    auc: float
    ci_low: float
    ci_high: float
    sample_count: int
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES
    bootstrap_unit: str = "RANDOMIZED_PAIR_BLOCK"

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "auc": self.auc,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "sample_count": self.sample_count,
            "bootstrap_resamples": self.bootstrap_resamples,
            "bootstrap_unit": self.bootstrap_unit,
        }


def frozen_models(seed: int) -> dict[str, ClassifierMixin]:
    return {
        "LOGISTIC_REGRESSION": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2_000, random_state=seed),
        ),
        "EXTRA_TREES": ExtraTreesClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            max_features="sqrt",
            n_jobs=1,
            random_state=seed,
        ),
        "HIST_GRADIENT_BOOSTING": HistGradientBoostingClassifier(
            learning_rate=0.08,
            max_iter=200,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=seed,
        ),
        "RBF_SVM": make_pipeline(
            StandardScaler(),
            SVC(C=1.0, gamma="scale", kernel="rbf", probability=True, random_state=seed),
        ),
    }


def group_bootstrap_auc(
    labels: np.ndarray,
    predictions: np.ndarray,
    groups: np.ndarray,
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    values: list[float] = []
    unique_groups = np.unique(groups)
    members = {group: np.flatnonzero(groups == group) for group in unique_groups}
    for group, indices in members.items():
        if tuple(np.bincount(labels[indices], minlength=2)) != (1, 1):
            raise ValueError(f"randomized block {group!r} must contain exactly one member of each class")
    for _ in range(resamples):
        sample = resample_whole_groups(unique_groups, members, generator)
        if np.unique(labels[sample]).size != 2:
            continue
        values.append(float(roc_auc_score(labels[sample], predictions[sample])))
    if len(values) < int(resamples * 0.99):
        raise RuntimeError("group bootstrap produced too many single-class resamples")
    low, high = np.quantile(np.asarray(values), [0.025, 0.975])
    return float(low), float(high)


def resample_whole_groups(
    unique_groups: np.ndarray,
    members: dict[object, np.ndarray],
    generator: np.random.Generator,
) -> np.ndarray:
    sampled_groups = generator.choice(unique_groups, size=len(unique_groups), replace=True)
    return np.concatenate([members[group] for group in sampled_groups])


def evaluate_binary_attack_family(
    vectors: Sequence[Sequence[float]],
    labels: Sequence[int],
    groups: Sequence[int],
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> list[AttackResult]:
    matrix = np.asarray(vectors, dtype=np.float64)
    target = np.asarray(labels, dtype=np.int64)
    group_values = np.asarray(groups, dtype=np.int64)
    if matrix.ndim != 2 or len(matrix) != len(target) or len(target) != len(group_values):
        raise ValueError("attack matrix, labels, and groups must align")
    counts = np.bincount(target, minlength=2)
    if tuple(counts) != (len(target) // 2, len(target) // 2):
        raise ValueError(f"binary timing task must be balanced, got {counts.tolist()}")
    splitter = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=seed)
    results: list[AttackResult] = []
    for offset, (name, model) in enumerate(frozen_models(seed).items()):
        probabilities = cross_val_predict(
            model,
            matrix,
            target,
            groups=group_values,
            cv=splitter,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]
        auc = float(roc_auc_score(target, probabilities))
        low, high = group_bootstrap_auc(
            target,
            probabilities,
            group_values,
            seed=seed + 10_000 * (offset + 1),
            resamples=resamples,
        )
        results.append(AttackResult(name, auc, low, high, len(target), resamples))
    return results


def conservative_best(results: Sequence[AttackResult]) -> AttackResult:
    if not results:
        raise ValueError("attack family is empty")
    return max(results, key=lambda item: (item.auc, item.ci_high, item.model))


def protected_pass(result: AttackResult) -> bool:
    return result.ci_high <= BINARY_EQUIVALENCE_LIMIT


def positive_control_informative(result: AttackResult) -> bool:
    return result.ci_low >= POSITIVE_CONTROL_LOWER_LIMIT


def sentinel_early_fail(result: AttackResult) -> bool:
    return result.auc >= 0.60 or result.ci_low > BINARY_EQUIVALENCE_LIMIT
