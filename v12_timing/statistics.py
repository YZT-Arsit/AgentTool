from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from sklearn.metrics import roc_auc_score

BOOTSTRAP_RESAMPLES = 10_000


@dataclass(frozen=True)
class BlockSplit:
    train_blocks: tuple[int, ...]
    eval_blocks: tuple[int, ...]

    def validate(self) -> "BlockSplit":
        if not self.train_blocks or not self.eval_blocks:
            raise ValueError("TRAIN and EVAL must both contain complete blocks")
        if set(self.train_blocks) & set(self.eval_blocks):
            raise ValueError("TRAIN and EVAL block partitions overlap")
        return self


def validate_matched_blocks(labels: Sequence[int], blocks: Sequence[int]) -> dict[int, np.ndarray]:
    target = np.asarray(labels, dtype=np.int64)
    groups = np.asarray(blocks, dtype=np.int64)
    if len(target) != len(groups) or not len(target):
        raise ValueError("labels and blocks must be nonempty and aligned")
    members = {int(group): np.flatnonzero(groups == group) for group in np.unique(groups)}
    for group, indices in members.items():
        if len(indices) != 2 or sorted(target[indices].tolist()) != [0, 1]:
            raise ValueError(f"matched block {group} must contain exactly one member of each class")
    return members


def deterministic_block_split(blocks: Sequence[int], *, seed_hex: str, train_fraction: float = 0.60) -> BlockSplit:
    unique = sorted(set(int(value) for value in blocks))
    if len(unique) < 2 or not 0 < train_fraction < 1:
        raise ValueError("block split needs at least two blocks and an interior TRAIN fraction")
    ordered = sorted(unique, key=lambda block: hashlib.sha256(f"{seed_hex}|B{block}".encode()).digest())
    count = min(len(unique) - 1, max(1, round(len(unique) * train_fraction)))
    return BlockSplit(tuple(sorted(ordered[:count])), tuple(sorted(ordered[count:]))).validate()


def partition_indices(blocks: Sequence[int], split: BlockSplit) -> tuple[np.ndarray, np.ndarray]:
    groups = np.asarray(blocks, dtype=np.int64)
    train = np.flatnonzero(np.isin(groups, split.train_blocks))
    evaluation = np.flatnonzero(np.isin(groups, split.eval_blocks))
    if len(train) + len(evaluation) != len(groups):
        raise ValueError("split does not account for every block")
    return train, evaluation


def distinguishability_auc(auc: float) -> float:
    value = float(auc)
    if not 0.0 <= value <= 1.0:
        raise ValueError("AUC must be in [0, 1]")
    return max(value, 1.0 - value)


def family_auc(labels: Sequence[int], predictions: Mapping[str, Sequence[float]]) -> tuple[float, dict[str, float]]:
    target = np.asarray(labels, dtype=np.int64)
    if set(target.tolist()) != {0, 1}:
        raise ValueError("AUC requires both protected classes")
    raw_aucs = {}
    for name, values in predictions.items():
        scores = np.asarray(values, dtype=np.float64)
        if len(scores) != len(target):
            raise ValueError("prediction vector does not align with labels")
        raw_aucs[name] = float(roc_auc_score(target, scores))
    if not raw_aucs:
        raise ValueError("classifier family is empty")
    oriented = {name: distinguishability_auc(value) for name, value in raw_aucs.items()}
    return max(oriented.values()), raw_aucs


def resample_complete_blocks(members: Mapping[int, np.ndarray], generator: np.random.Generator) -> np.ndarray:
    unique = np.asarray(sorted(members), dtype=np.int64)
    selected = generator.choice(unique, size=len(unique), replace=True)
    return np.concatenate([members[int(group)] for group in selected])


def bootstrap_family_auc(labels: Sequence[int], predictions: Mapping[str, Sequence[float]],
                         blocks: Sequence[int], *, seed: int,
                         resamples: int = BOOTSTRAP_RESAMPLES) -> dict[str, object]:
    target = np.asarray(labels, dtype=np.int64)
    members = validate_matched_blocks(target, blocks)
    vectors = {name: np.asarray(values, dtype=np.float64) for name, values in predictions.items()}
    point, raw_component = family_auc(target, vectors)
    oriented_component = {name: distinguishability_auc(value) for name, value in raw_component.items()}
    generator = np.random.default_rng(seed)
    values = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        sample = resample_complete_blocks(members, generator)
        values[index] = family_auc(target[sample], {name: vector[sample] for name, vector in vectors.items()})[0]
    low, high = np.quantile(values, [0.025, 0.975])
    return {
        "model_family_distinguishability_auc": point,
        "raw_component_aucs": raw_component,
        "component_distinguishability_aucs": oriented_component,
        "ci_low": float(low), "ci_high": float(high),
        "bootstrap_unit": "MATCHED_EVAL_BLOCK", "bootstrap_resamples": int(resamples),
        "refit_inside_bootstrap": False,
    }


def paired_label_randomization(labels: Sequence[int], blocks: Sequence[int], *, seed: int) -> np.ndarray:
    target = np.asarray(labels, dtype=np.int64).copy()
    members = validate_matched_blocks(target, blocks)
    generator = np.random.default_rng(seed)
    for indices in members.values():
        if generator.integers(0, 2):
            target[indices] = target[indices[::-1]]
    return target


def approximate_chance_auc_precision(eval_blocks: int) -> dict[str, float | int | str]:
    if eval_blocks < 2:
        raise ValueError("at least two EVAL blocks are required")
    # Mann-Whitney AUC null approximation with n0=n1=eval_blocks. This is a
    # planning approximation, not a substitute for independent blocks.
    standard_error = math.sqrt((2 * eval_blocks + 1) / (12 * eval_blocks * eval_blocks))
    half_width = 1.96 * standard_error
    return {
        "eval_blocks": eval_blocks, "sessions": 2 * eval_blocks,
        "approximate_standard_error": standard_error,
        "approximate_95pct_half_width": half_width,
        "assumption": "single fixed AUC under chance; family-max interval may be wider",
    }
