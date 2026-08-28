from __future__ import annotations

import csv
import hashlib
import json
import random
import statistics
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, StratifiedShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from agent_control_virtualization.runtime import AgentControlExecutor, structural_signature
from .pir_backend import PIRRequest, SimplePIRArtifacts, read_raw_queries, recovered_capsules, run_simplepir


def build_sequences(episodes_per_profile: int = 12, rounds: int = 100) -> list[PIRRequest]:
    rng = random.Random(7713)
    episodes: list[list[PIRRequest]] = []
    for profile in range(8):
        for episode_number in range(episodes_per_profile):
            episode = f"M{profile}-E{episode_number:02d}"
            if profile == 0:
                sequence = [17] * rounds
            elif profile == 1:
                sequence = [17] * rounds
                sequence[rng.randrange(rounds)] = 23
            elif profile == 2:
                sequence = [17] * (rounds // 2) + [23] * (rounds - rounds // 2)
                rng.shuffle(sequence)
            elif profile == 3:
                sequence = [100 + rng.randrange(10) for _ in range(rounds)]
            elif profile == 4:
                sequence = [10 if index % 2 == 0 else 11 for index in range(rounds)]
            elif profile == 5:
                sequence = [10 if index % 2 == 0 else 12 for index in range(rounds)]
            elif profile == 6:
                target = 30 + episode_number % 10
                sequence = [target] * rounds
            else:
                sequence = [17] * rounds
            episodes.append([PIRRequest(episode, index, agent, f"M{profile}")
                             for index, agent in enumerate(sequence)])
    # Avoid temporal drift becoming a profile label while preserving the order
    # within each 100-round sequence.
    rng.shuffle(episodes)
    return [request for episode in episodes for request in episode]


def _query_features(payload: bytes, server: dict[str, object]) -> np.ndarray:
    values = np.frombuffer(payload[16:], dtype="<u4")
    byte_values = np.frombuffer(payload, dtype=np.uint8)
    hist = np.bincount(byte_values // 16, minlength=16) / len(byte_values)
    sample_indices = np.linspace(0, len(values) - 1, 24, dtype=int)
    sampled = values[sample_indices].astype(np.float64) / (2**32 - 1)
    digest = np.frombuffer(hashlib.sha256(payload).digest()[:8], dtype=np.uint8) / 255.0
    summary = np.array([
        len(payload), float(values.mean()) / (2**32 - 1), float(values.std()) / (2**32 - 1),
        float(server["query_bytes"]), float(server["answer_bytes"]),
    ])
    return np.concatenate((summary, hist, sampled, digest))


def _split_scores(X: np.ndarray, y: np.ndarray, groups: np.ndarray, model, binary: bool) -> tuple[float, float]:
    scores: list[float] = []
    accuracies: list[float] = []
    splitter = GroupShuffleSplit(n_splits=5, test_size=0.3, random_state=191)
    for train, test in splitter.split(X, y, groups):
        fitted = clone(model).fit(X[train], y[train])
        predicted = fitted.predict(X[test])
        accuracies.append(balanced_accuracy_score(y[test], predicted) if binary else accuracy_score(y[test], predicted))
        if binary:
            probability = fitted.predict_proba(X[test])[:, list(fitted.classes_).index(1)]
            scores.append(roc_auc_score(y[test], probability))
        else:
            scores.append(f1_score(y[test], predicted, average="macro"))
    return statistics.mean(scores), statistics.mean(accuracies)


def _permutation_baseline(X: np.ndarray, y: np.ndarray, groups: np.ndarray, model, binary: bool) -> tuple[float, float]:
    rng = np.random.default_rng(991)
    observed, _ = _split_scores(X, y, groups, model, binary)
    scores: list[float] = []
    for _ in range(20):
        shuffled = rng.permutation(y)
        score, _ = _split_scores(X, shuffled, groups, model, binary)
        scores.append(score)
    p_value = (1 + sum(score >= observed for score in scores)) / (len(scores) + 1)
    return statistics.mean(scores), p_value


def _models():
    return {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "RandomForest": RandomForestClassifier(n_estimators=60, max_depth=8, random_state=7, n_jobs=1),
    }


def _evaluate_binary(name: str, feature_set: str, X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for model_name, model in _models().items():
        auc, balanced = _split_scores(X, y, groups, model, True)
        permutation, p_value = _permutation_baseline(X, y, groups, model, True)
        rows.append({"attack": name, "feature_set": feature_set, "model": model_name, "metric": "AUC",
                     "score": auc, "balanced_accuracy": balanced,
                     "permutation_baseline": permutation, "permutation_p_value": p_value,
                     "samples": len(y), "chance": 0.5})
    return rows


def _episode_features(requests: list[PIRRequest], query_features: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    by_episode: dict[str, list[int]] = {}
    profile: dict[str, str] = {}
    for position, request in enumerate(requests):
        by_episode.setdefault(request.episode, []).append(position)
        profile[request.episode] = request.private_class
    features: dict[str, np.ndarray] = {}
    for episode, positions in by_episode.items():
        values = query_features[positions]
        means = values.mean(axis=0)
        stds = values.std(axis=0)
        adjacent = np.abs(np.diff(values, axis=0)).mean(axis=0)
        features[episode] = np.concatenate((means, stds, adjacent))
    return features, profile


def analyze_multiround(requests: list[PIRRequest], artifacts: SimplePIRArtifacts,
                       output_csv: Path, host_trace_path: Path) -> list[dict[str, object]]:
    raw = read_raw_queries(artifacts.raw_query_path)
    if len(raw) != len(requests) or len(artifacts.server_trace) != len(requests):
        raise AssertionError("trace alignment failure")
    raw_features = np.vstack([_query_features(payload, server)
                              for payload, server in zip(raw, artifacts.server_trace)])
    timing_features = np.array([[float(server["answer_ms"])] for server in artifacts.server_trace])
    results: list[dict[str, object]] = []

    def attacks_for(feature_set: str, query_features: np.ndarray) -> None:
        rng = random.Random(101)
        by_index: dict[int, list[int]] = {}
        for position, request in enumerate(requests):
            by_index.setdefault(request.index, []).append(position)
        same_pairs: list[tuple[int, int]] = []
        different_pairs: list[tuple[int, int]] = []
        eligible = [positions for positions in by_index.values() if len(positions) >= 2]
        for _ in range(2000):
            positions = rng.choice(eligible); same_pairs.append(tuple(rng.sample(positions, 2)))
            left, right = rng.sample(list(by_index), 2)
            different_pairs.append((rng.choice(by_index[left]), rng.choice(by_index[right])))
        pairs = same_pairs + different_pairs
        X = np.vstack([np.abs(query_features[a] - query_features[b]) for a, b in pairs])
        y = np.array([1] * len(same_pairs) + [0] * len(different_pairs))
        groups = np.array([requests[a].episode for a, _ in pairs])
        results.extend(_evaluate_binary("REPEATED_TARGET_LINKABILITY", feature_set, X, y, groups))

        episode_values, profiles = _episode_features(requests, query_features)
        def episode_binary(name: str, left: str, right: str) -> None:
            episodes = [episode for episode, profile in profiles.items() if profile in (left, right)]
            Xep = np.vstack([episode_values[episode] for episode in episodes])
            yep = np.array([int(profiles[episode] == right) for episode in episodes])
            results.extend(_evaluate_binary(name, feature_set, Xep, yep, np.array(episodes)))
        episode_binary("FREQUENCY_RECOVERY_M0_VS_M2", "M0", "M2")
        episode_binary("RARE_AGENT_DETECTION_M0_VS_M1", "M0", "M1")
        episode_binary("TRANSITION_PATTERN_M4_VS_M5", "M4", "M5")

        m3_positions = [i for i, request in enumerate(requests) if request.private_class == "M3"]
        Xid = query_features[m3_positions]
        yid = np.array([requests[i].index for i in m3_positions])
        gid = np.array([requests[i].episode for i in m3_positions])
        for model_name, model in _models().items():
            macro_f1, accuracy = _split_scores(Xid, yid, gid, model, False)
            permutation, p_value = _permutation_baseline(Xid, yid, gid, model, False)
            results.append({"attack": "AGENT_ID_10_WAY", "feature_set": feature_set,
                            "model": model_name, "metric": "MACRO_F1",
                            "score": macro_f1, "balanced_accuracy": accuracy,
                            "permutation_baseline": permutation, "permutation_p_value": p_value,
                            "samples": len(yid), "chance": 0.1})

    for feature_set, values in (("RAW_QUERY", raw_features), ("TIMING", timing_features),
                                ("ALL", np.hstack((raw_features, timing_features)))):
        attacks_for(feature_set, values)
    for attack, chance in (("REPEATED_TARGET_LINKABILITY", 0.5),
                           ("FREQUENCY_RECOVERY_M0_VS_M2", 0.5),
                           ("RARE_AGENT_DETECTION_M0_VS_M1", 0.5),
                           ("TRANSITION_PATTERN_M4_VS_M5", 0.5),
                           ("AGENT_ID_10_WAY", 0.1)):
        results.append({"attack": attack, "feature_set": "STRUCTURAL_SIZE", "model": "SYMBOLIC",
                        "metric": "EXACT_EQUALITY", "score": chance, "balanced_accuracy": chance,
                        "permutation_baseline": chance, "permutation_p_value": 1.0,
                        "samples": len(requests), "chance": chance})

    # Actual B2 path: every recovered PIR row is parsed and consumed by the
    # common executor; only the server trace plus fixed executor frames are host-visible.
    host_rows: list[dict[str, object]] = []
    signatures: set[str] = set()
    for ordinal, (request, capsule, server) in enumerate(zip(requests, recovered_capsules(artifacts), artifacts.server_trace)):
        if capsule.logical_agent_id != request.index:
            raise AssertionError("real PIR capsule did not reach the intended control path")
        executor = AgentControlExecutor({capsule.logical_agent_id: capsule})
        frames = executor.fixed_transcript(capsule.logical_agent_id)
        signatures.add(structural_signature(frames))
        host_rows.append({"ordinal": ordinal, "pir": server, "control_frames": frames})
    with host_trace_path.open("w", encoding="utf-8") as handle:
        for row in host_rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    if len(signatures) != 1:
        raise AssertionError("common executor shape diverged")

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader(); writer.writerows(results)
    return results


def run_primary(root: Path, registry: Path, output_dir: Path) -> tuple[SimplePIRArtifacts, list[dict[str, object]]]:
    requests = build_sequences(episodes_per_profile=20)
    artifacts = run_simplepir(root, registry, 1000, requests, output_dir / "pir")
    results = analyze_multiround(requests, artifacts, output_dir / "MULTIROUND_ATTACK_RESULTS.csv",
                                 output_dir / "host_visible_full_path.jsonl")
    return artifacts, results


def run_cross_session(root: Path, registry: Path, output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sessions: list[tuple[str, int, np.ndarray]] = []
    targets = [17, 101, 102, 17, 101, 102, 17, 101, 102, 17, 101, 102]
    for session_number, target in enumerate(targets):
        session = f"SESSION-{session_number}"
        requests = [PIRRequest(session, index, target, "CROSS_SESSION") for index in range(30)]
        artifacts = run_simplepir(root, registry, 1000, requests, output_dir / session)
        raw = read_raw_queries(artifacts.raw_query_path)
        features = np.vstack([_query_features(payload, server)
                              for payload, server in zip(raw, artifacts.server_trace)])
        sessions.append((session, target, features))
    X: list[np.ndarray] = []
    y: list[int] = []
    groups: list[str] = []
    for left in range(len(sessions)):
        for right in range(left + 1, len(sessions)):
            for sample in range(20):
                X.append(np.abs(sessions[left][2][sample] - sessions[right][2][sample]))
                y.append(int(sessions[left][1] == sessions[right][1]))
                groups.append(f"{sessions[left][0]}:{sessions[right][0]}")
    rows = _evaluate_binary("CROSS_SESSION_LINKABILITY", "RAW_QUERY", np.vstack(X),
                            np.array(y), np.array(groups))
    rows.append({"attack": "CROSS_SESSION_LINKABILITY", "feature_set": "STRUCTURAL_SIZE",
                 "model": "SYMBOLIC", "metric": "EXACT_EQUALITY", "score": 0.5,
                 "balanced_accuracy": 0.5, "permutation_baseline": 0.5,
                 "permutation_p_value": 1.0, "samples": len(y), "chance": 0.5})
    path = output_dir / "cross_session_attack_results.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    return rows
