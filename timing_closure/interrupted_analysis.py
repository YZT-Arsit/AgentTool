from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from timing_closure.analysis import (
    _episode_rows,
    binary_holdout,
    csv_rows,
    gateway_features,
    jsonl,
    pir_query_pair_dataset,
    write_csv,
)


def _models(seed: int) -> dict[str, object]:
    return {
        "LogisticRegression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed)
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=120, max_depth=8, random_state=seed, n_jobs=1
        ),
    }


def _group_indices(groups: np.ndarray) -> dict[str, np.ndarray]:
    return {
        str(group): np.flatnonzero(groups == group)
        for group in sorted(set(str(value) for value in groups))
    }


def grouped_binary_holdout(
    attack: str,
    Xdev: np.ndarray,
    ydev: np.ndarray,
    Xtest: np.ndarray,
    ytest: np.ndarray,
    test_groups: np.ndarray,
    observation_count: int,
    seed: int,
    resamples: int = 2000,
) -> list[dict[str, object]]:
    """Evaluate frozen holdout predictions with episode-level uncertainty.

    Blocks from one source episode (or episode pair) are correlated. Bootstrap
    and permutation therefore resample/permute whole groups, never individual
    blocks. Models are fit on development traces only.
    """

    grouped = _group_indices(test_groups)
    group_names = np.array(list(grouped))
    group_labels = np.array([int(ytest[grouped[name][0]]) for name in group_names])
    if any(np.any(ytest[grouped[name]] != group_labels[i]) for i, name in enumerate(group_names)):
        raise ValueError("each uncertainty group must have one label")

    output: list[dict[str, object]] = []
    for model_offset, (model_name, base) in enumerate(_models(seed).items()):
        fitted = clone(base).fit(Xdev, ydev)
        class_index = list(fitted.classes_).index(1)
        prediction = fitted.predict_proba(Xtest)[:, class_index]
        observed = float(roc_auc_score(ytest, prediction))
        rng = np.random.default_rng(seed + 1009 + model_offset)

        bootstrap_scores: list[float] = []
        for _ in range(resamples):
            sampled_names = rng.choice(group_names, len(group_names), replace=True)
            sampled_index = np.concatenate([grouped[str(name)] for name in sampled_names])
            if len(np.unique(ytest[sampled_index])) == 2:
                bootstrap_scores.append(float(roc_auc_score(ytest[sampled_index], prediction[sampled_index])))
        ci_low, ci_high = (float(value) for value in np.quantile(bootstrap_scores, [0.025, 0.975]))

        permutation_scores: list[float] = []
        for _ in range(resamples):
            shuffled = rng.permutation(group_labels)
            permuted_y = ytest.copy()
            for name, label in zip(group_names, shuffled):
                permuted_y[grouped[str(name)]] = label
            permutation_scores.append(float(roc_auc_score(permuted_y, prediction)))
        observed_advantage = abs(observed - 0.5)
        permutation_advantages = [abs(score - 0.5) for score in permutation_scores]
        p_value = (1 + sum(value >= observed_advantage for value in permutation_advantages)) / (
            len(permutation_advantages) + 1
        )
        output.append(
            {
                "attack": attack,
                "observation_count": observation_count,
                "model": model_name,
                "metric": "AUC",
                "score": observed,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "permutation_baseline_mean": float(np.mean(permutation_scores)),
                "permutation_baseline_ci_low": float(np.quantile(permutation_scores, 0.025)),
                "permutation_baseline_ci_high": float(np.quantile(permutation_scores, 0.975)),
                "permutation_p_value": p_value,
                "test_samples": len(ytest),
                "test_groups": len(group_names),
                "chance": 0.5,
                "engineering_gate": bool(observed <= 0.55 and ci_low <= 0.5 <= ci_high and p_value > 0.05),
                "split": "FROZEN_CONFIRMATORY_GROUPED",
                "resamples": resamples,
            }
        )
    return output


def _pir_blocks(path: Path, observation_count: int) -> list[dict[str, object]]:
    trace = jsonl(path / "server_visible_trace.jsonl")
    private = csv_rows(path / "private_queries.csv")
    positions: dict[str, list[int]] = {}
    for index, row in enumerate(private):
        if row["class"].split(":", 1)[0] not in {"M0", "M6"}:
            continue
        positions.setdefault(row["episode"], []).append(index)

    blocks: list[dict[str, object]] = []
    for episode, indices in sorted(positions.items()):
        targets = {int(private[index]["index"]) for index in indices}
        if len(targets) != 1:
            raise ValueError(f"constant-target profile changed within {episode}")
        target = next(iter(targets))
        for block_ordinal, start in enumerate(range(0, len(indices), observation_count)):
            selected = indices[start : start + observation_count]
            if len(selected) != observation_count:
                continue
            rows = [trace[index] for index in selected]
            request_slip = np.array(
                [(int(row["request_arrival_ns"]) - int(row["scheduled_ns"])) / 1e6 for row in rows]
            )
            answer_duration = np.array(
                [(int(row["answer_ready_ns"]) - int(row["request_arrival_ns"])) / 1e6 for row in rows]
            )
            # Same two frozen PIR timing fields, now summarized over a fixed block.
            values = np.concatenate(
                (
                    request_slip,
                    answer_duration,
                    [
                        request_slip.mean(),
                        request_slip.std(),
                        np.quantile(request_slip, 0.95),
                        request_slip.max(),
                        answer_duration.mean(),
                        answer_duration.std(),
                        np.quantile(answer_duration, 0.95),
                        answer_duration.max(),
                    ],
                )
            )
            blocks.append(
                {
                    "episode": episode,
                    "block": block_ordinal,
                    "target": target,
                    "features": values,
                }
            )
    return blocks


def pir_repeated_observation_pairs(
    path: Path, observation_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pair matching-position blocks from distinct constant-target episodes."""

    blocks = _pir_blocks(path, observation_count)
    by_position: dict[int, list[dict[str, object]]] = {}
    for block in blocks:
        by_position.setdefault(int(block["block"]), []).append(block)
    X: list[np.ndarray] = []
    y: list[int] = []
    groups: list[str] = []
    for position, values in sorted(by_position.items()):
        for left_index, left in enumerate(values):
            for right in values[left_index + 1 :]:
                if left["episode"] == right["episode"]:
                    continue
                X.append(abs(np.asarray(left["features"]) - np.asarray(right["features"])))
                y.append(int(left["target"] == right["target"]))
                episode_pair = "|".join(sorted((str(left["episode"]), str(right["episode"]))))
                groups.append(episode_pair)
    return np.vstack(X), np.asarray(y), np.asarray(groups)


def _gateway_blocks(
    path: Path, observation_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    traces = _episode_rows(path)
    truth = [row for row in csv_rows(path / "private_ground_truth.csv") if row["family"] == "TOOL_SEQUENCE"]
    X: list[np.ndarray] = []
    y: list[str] = []
    groups: list[str] = []
    for row in truth:
        token = int(row["episode_token"])
        # Only the 100 real-action slots are in the frozen sequence definition;
        # padding slots 101--200 are deliberately excluded from sequence attacks.
        real_rows = traces[token][:100]
        for start in range(0, len(real_rows), observation_count):
            block = real_rows[start : start + observation_count]
            if len(block) != observation_count:
                continue
            X.append(gateway_features(block, "ALL"))
            y.append(row["label"])
            groups.append(str(token))
    return np.vstack(X), np.asarray(y), np.asarray(groups)


def _select_grouped_binary(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, left: str, right: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = np.isin(y, [left, right])
    return X[mask], (y[mask] == right).astype(int), groups[mask]


def run_interrupted_analysis(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    results = root / "results_timing_closure"
    dev_pir = results / "development_pir"
    test_pir = results / "confirmatory_pir"
    dev_tool = results / "development_tool_sequences"
    test_tool = results / "confirmatory_final_tool_sequences"

    pir_rows: list[dict[str, object]] = []
    # Preserve and restate the exact interrupted-run single-observation analysis.
    Xdev, ydev = pir_query_pair_dataset(dev_pir, 2000, 71)
    Xtest, ytest = pir_query_pair_dataset(test_pir, 2000, 72)
    for row in binary_holdout("PIR_REPEATED_TARGET_LINKABILITY", Xdev, ydev, Xtest, ytest):
        row.update(
            {
                "observation_count": 1,
                "test_groups": "NOT_APPLICABLE_SINGLE_QUERY_PAIRS",
                "feature_set": "REQUEST_SLIP+ANSWER_DURATION",
                "split": "FROZEN_CONFIRMATORY",
            }
        )
        pir_rows.append(row)

    for observation_count in (10, 50, 100):
        Xdev, ydev, _ = pir_repeated_observation_pairs(dev_pir, observation_count)
        Xtest, ytest, groups = pir_repeated_observation_pairs(test_pir, observation_count)
        rows = grouped_binary_holdout(
            "PIR_REPEATED_TARGET_LINKABILITY_AGGREGATED",
            Xdev,
            ydev,
            Xtest,
            ytest,
            groups,
            observation_count,
            seed=440 + observation_count,
        )
        for row in rows:
            row["feature_set"] = "REQUEST_SLIP+ANSWER_DURATION"
        pir_rows.extend(rows)

    tool_rows: list[dict[str, object]] = []
    attacks = {
        "TOOL_SEQUENCE_FREQUENCY": ("TSEQ0", "TSEQ2"),
        "TOOL_SEQUENCE_RARE_EVENT": ("TSEQ0", "TSEQ1"),
        "TOOL_SEQUENCE_TRANSITION": ("TSEQ3", "TSEQ4"),
    }
    for observation_count in (10, 50, 100):
        Xdev_all, ydev_all, groups_dev = _gateway_blocks(dev_tool, observation_count)
        Xtest_all, ytest_all, groups_test = _gateway_blocks(test_tool, observation_count)
        for attack, (left, right) in attacks.items():
            Xdev, ydev, _ = _select_grouped_binary(Xdev_all, ydev_all, groups_dev, left, right)
            Xtest, ytest, groups = _select_grouped_binary(Xtest_all, ytest_all, groups_test, left, right)
            rows = grouped_binary_holdout(
                attack,
                Xdev,
                ydev,
                Xtest,
                ytest,
                groups,
                observation_count,
                seed=730 + observation_count,
            )
            for row in rows:
                row["feature_set"] = "FROZEN_SOCKET_TIMING_ALL"
            tool_rows.extend(rows)

    write_csv(root / "PIR_REPEATED_OBSERVATION_RESULTS.csv", pir_rows)
    write_csv(root / "TOOL_SEQUENCE_OBSERVATION_RESULTS.csv", tool_rows)
    return pir_rows, tool_rows
