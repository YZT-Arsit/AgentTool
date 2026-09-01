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
    if set(groups.tolist()) != set(split.train_blocks) | set(split.eval_blocks):
        raise ValueError("split block inventory does not exactly match the dataset")
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


def selected_model_eval_auc(labels: Sequence[int], oriented_scores: Sequence[float]) -> float:
    """AUC for the one model and score orientation frozen using TRAIN only."""

    target = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(oriented_scores, dtype=np.float64)
    if len(target) != len(scores) or set(target.tolist()) != {0, 1}:
        raise ValueError("selected-model EVAL AUC requires aligned scores and both classes")
    if not np.all(np.isfinite(scores)):
        raise ValueError("selected-model EVAL scores must be finite")
    return float(roc_auc_score(target, scores))


def matched_block_bootstrap_auc_values(
    labels: Sequence[int],
    oriented_scores: Sequence[float],
    blocks: Sequence[int],
    *,
    generator: np.random.Generator,
    resamples: int = BOOTSTRAP_RESAMPLES,
    chunk_size: int = 512,
) -> np.ndarray:
    """Return fixed-score AUCs after resampling complete matched blocks.

    Sampling block multiplicities from the corresponding multinomial is
    exactly equivalent to drawing the same number of blocks with replacement.
    The vectorized weighted-rank calculation preserves ties and never creates
    a partial block.
    """

    target = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(oriented_scores, dtype=np.float64)
    groups = np.asarray(blocks, dtype=np.int64)
    members = validate_matched_blocks(target, groups)
    if len(scores) != len(target) or not np.all(np.isfinite(scores)):
        raise ValueError("fixed EVAL scores must be finite and aligned")
    if resamples < 1 or chunk_size < 1:
        raise ValueError("bootstrap resamples and chunk size must be positive")

    unique = np.asarray(sorted(members), dtype=np.int64)
    block_position = {int(block): index for index, block in enumerate(unique)}
    observation_blocks = np.asarray([block_position[int(block)] for block in groups], dtype=np.int64)
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    sorted_labels = target[order]
    sorted_blocks = observation_blocks[order]
    group_starts = np.concatenate((
        np.asarray([0], dtype=np.int64),
        np.flatnonzero(sorted_scores[1:] != sorted_scores[:-1]).astype(np.int64) + 1,
    ))
    block_count = len(unique)
    probabilities = np.full(block_count, 1.0 / block_count, dtype=np.float64)
    output = np.empty(resamples, dtype=np.float64)
    for start in range(0, resamples, chunk_size):
        stop = min(resamples, start + chunk_size)
        multiplicity = generator.multinomial(block_count, probabilities, size=stop - start)
        observation_weights = multiplicity[:, sorted_blocks]
        positive = observation_weights * sorted_labels
        negative = observation_weights * (1 - sorted_labels)
        positive_by_score = np.add.reduceat(positive, group_starts, axis=1)
        negative_by_score = np.add.reduceat(negative, group_starts, axis=1)
        negative_before = np.cumsum(negative_by_score, axis=1) - negative_by_score
        numerator = np.sum(
            positive_by_score * (negative_before + 0.5 * negative_by_score), axis=1
        )
        output[start:stop] = numerator / float(block_count * block_count)
    return output


def bootstrap_selected_model_auc(
    labels: Sequence[int],
    oriented_scores: Sequence[float],
    blocks: Sequence[int],
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    """Decisive fixed-model, fixed-orientation matched-EVAL-block inference."""

    point = selected_model_eval_auc(labels, oriented_scores)
    values = matched_block_bootstrap_auc_values(
        labels,
        oriented_scores,
        blocks,
        generator=np.random.default_rng(seed),
        resamples=resamples,
    )
    ci_low, ci_high = np.quantile(values, [0.025, 0.975])
    return {
        "selected_model_eval_auc": point,
        "auc_ucb95_one_sided": float(np.quantile(values, 0.95)),
        "auc_lcb95_one_sided": float(np.quantile(values, 0.05)),
        "ci95_two_sided_low": float(ci_low),
        "ci95_two_sided_high": float(ci_high),
        "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
        "bootstrap_resamples": int(resamples),
        "model_refit_inside_bootstrap": False,
        "model_reselected_inside_bootstrap": False,
        "orientation_reselected_inside_bootstrap": False,
        "post_hoc_eval_orientation": False,
    }


def paired_label_randomization(labels: Sequence[int], blocks: Sequence[int], *, seed: int) -> np.ndarray:
    target = np.asarray(labels, dtype=np.int64).copy()
    members = validate_matched_blocks(target, blocks)
    generator = np.random.default_rng(seed)
    for indices in members.values():
        if generator.integers(0, 2):
            target[indices] = target[indices[::-1]]
    return target


def paired_auc_randomization_test(
    labels: Sequence[int],
    oriented_scores: Sequence[float],
    blocks: Sequence[int],
    *,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float | int | str]:
    """Secondary null diagnostic using independent within-pair label swaps."""

    target = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(oriented_scores, dtype=np.float64)
    members = validate_matched_blocks(target, blocks)
    observed = selected_model_eval_auc(target, scores)
    generator = np.random.default_rng(seed)
    exceedances = 0
    for _ in range(resamples):
        randomized = target.copy()
        for indices in members.values():
            if generator.integers(0, 2):
                randomized[indices] = randomized[indices[::-1]]
        exceedances += selected_model_eval_auc(randomized, scores) >= observed
    return {
        "observed_auc": observed,
        "one_sided_randomization_p": (exceedances + 1.0) / (resamples + 1.0),
        "randomization_resamples": int(resamples),
        "randomization_unit": "WITHIN_COMPLETE_MATCHED_BLOCK_LABEL_SWAP",
        "role": "SECONDARY_NULL_CONSISTENCY_DIAGNOSTIC",
    }


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
