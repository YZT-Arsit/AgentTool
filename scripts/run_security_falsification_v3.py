from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canonical_v3.runner import run_canonical_gateway
from canonical_v3.workflows import (llm_effect_tool, llm_read_tool,
                                    llm_read_tool_variant, logical_handoff,
                                    private_branch)
from privacy_kernel.protocol import CanonicalProfile


def profile() -> CanonicalProfile:
    return CanonicalProfile("CANONICAL_V3_FALSIFICATION", 1024, 3, 6,
                            40_000_000, 40_000_000, 8_000_000,
                            350_000_000, 60_000_000)


def public_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def feature(rows: list[dict[str, object]]) -> list[float]:
    # Deliberately limited to declared structural/size metadata. Timing and
    # ciphertext bytes are separate claims and are not silently dropped after testing.
    directions = [str(row["direction"]) for row in rows]
    slots = [int(row["slot"]) for row in rows]
    sessions = [int(row["session"]) for row in rows]
    sizes = [int(row["frame_bytes"]) for row in rows]
    return [
        len(rows), directions.count("REQUEST"), directions.count("RESPONSE"),
        len(set(slots)), len(set(sessions)), min(sizes), max(sizes), sum(sizes),
        len({str(row["destination"]) for row in rows}),
    ]


def bootstrap_accuracy(y: np.ndarray, prediction: np.ndarray, rng: np.random.Generator,
                       samples: int = 2000) -> tuple[float, float]:
    values = []
    for _ in range(samples):
        selected = rng.integers(0, len(y), len(y))
        values.append(accuracy_score(y[selected], prediction[selected]))
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def evaluate(name: str, records: list[dict[str, object]], label_key: str,
             binary: bool, rng: np.random.Generator) -> list[dict[str, object]]:
    train = [row for row in records if int(row["repetition"]) < 4]
    test = [row for row in records if int(row["repetition"]) >= 4]
    labels = sorted({str(row[label_key]) for row in records})
    encode = {label: index for index, label in enumerate(labels)}
    x_train = np.asarray([row["features"] for row in train], dtype=float)
    x_test = np.asarray([row["features"] for row in test], dtype=float)
    y_train = np.asarray([encode[str(row[label_key])] for row in train])
    y_test = np.asarray([encode[str(row[label_key])] for row in test])
    outputs: list[dict[str, object]] = []
    models = {
        "LogisticRegression": LogisticRegression(max_iter=2000, random_state=73),
        "RandomForestClassifier": RandomForestClassifier(n_estimators=200, random_state=73),
    }
    for model_name, model in models.items():
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        accuracy = float(accuracy_score(y_test, predicted))
        ci_low, ci_high = bootstrap_accuracy(y_test, predicted, rng)
        metric, value, chance = "accuracy", accuracy, 1 / len(labels)
        if binary:
            metric = "roc_auc"
            value = float(roc_auc_score(y_test, model.predict_proba(x_test)[:, 1]))
            # A constant score always has exactly AUC 0.5; retain the accuracy
            # bootstrap only as an uncertainty diagnostic over class predictions.
            chance = 0.5
        null = []
        for _ in range(500):
            shuffled = rng.permutation(y_train)
            candidate = (LogisticRegression(max_iter=2000, random_state=73)
                         if model_name == "LogisticRegression" else
                         RandomForestClassifier(n_estimators=50, random_state=73))
            candidate.fit(x_train, shuffled)
            if binary:
                null.append(roc_auc_score(y_test, candidate.predict_proba(x_test)[:, 1]))
            else:
                null.append(accuracy_score(y_test, candidate.predict(x_test)))
        advantage = abs(value - chance)
        p_value = float((1 + sum(abs(item - chance) >= advantage for item in null)) / (len(null) + 1))
        outputs.append({
            "attack": name, "classes": len(labels), "episodes": len(records),
            "model": model_name, "metric": metric, "value": value,
            "accuracy_bootstrap_ci_low": ci_low, "accuracy_bootstrap_ci_high": ci_high,
            "analytical_chance": chance, "permutation_mean": float(np.mean(null)),
            "permutation_p_value": p_value, "two_sided_advantage": advantage,
            "symbolic_feature_equality": len({tuple(row["features"]) for row in records}) == 1,
            "status": "NO_STRUCTURAL_SIZE_SIGNAL" if advantage == 0 else "RESIDUAL_SIGNAL",
        })
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    fixtures = [
        ("READ_BASE", "MODEL_TOOL_MODEL", llm_read_tool()),
        ("EFFECT", "MODEL_TOOL_MODEL", llm_effect_tool()),
        ("HANDOFF", "HANDOFF_MODEL", logical_handoff()),
        ("READ_ALPHA", "MODEL_TOOL_MODEL", llm_read_tool_variant(41, 4101, "READ_ALPHA")),
        ("READ_BETA", "MODEL_TOOL_MODEL", llm_read_tool_variant(42, 4201, "READ_BETA")),
        ("BRANCH_FALSE", "PRIVATE_BRANCH", private_branch(False)),
        ("BRANCH_TRUE", "PRIVATE_BRANCH", private_branch(True)),
    ]
    records: list[dict[str, object]] = []
    private_truth: list[dict[str, object]] = []
    for repetition in range(6):
        for private_label, action_family, fixture in fixtures:
            case = output / "raw" / f"r{repetition}_{private_label.lower()}"
            result = run_canonical_gateway(ROOT, case, profile(), fixture.kernel())
            visible = public_rows(case / "agentcloud_public_trace.jsonl")
            if not result["returned"] or result["dummy_heavy_operations"] != 0:
                raise AssertionError("functional/heavy-operation invariant failed")
            records.append({
                "episode": f"r{repetition}-{private_label}", "repetition": repetition,
                "features": feature(visible), "agent_label": private_label,
                "action_family": action_family,
            })
            private_truth.append({
                "episode": f"r{repetition}-{private_label}", "repetition": repetition,
                "private_agent_label": private_label, "private_action_family": action_family,
            })
    with (output / "host_visible_features.jsonl").open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps({"episode": row["episode"], "repetition": row["repetition"],
                                     "features": row["features"]}, separators=(",", ":")) + "\n")
    with (output / "private_ground_truth.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(private_truth[0]))
        writer.writeheader(); writer.writerows(private_truth)

    rng = np.random.default_rng(20260827)
    results = evaluate("agent_identity_7class", records, "agent_label", False, rng)
    results += evaluate("tool_identity_alpha_vs_beta",
                        [row for row in records if row["agent_label"] in {"READ_ALPHA", "READ_BETA"}],
                        "agent_label", True, rng)
    results += evaluate("private_branch_state",
                        [row for row in records if str(row["agent_label"]).startswith("BRANCH_")],
                        "agent_label", True, rng)
    action_records = [row for row in records if row["agent_label"] in
                      {"READ_BASE", "HANDOFF", "BRANCH_FALSE"}]
    results += evaluate("private_action_family_3class", action_records, "action_family", False, rng)
    for attack in ("repeated_agent", "agent_frequency", "rare_agent", "transition_pattern",
                   "cross_session_linkability"):
        results.append({
            "attack": attack, "classes": "", "episodes": 0, "model": "NOT_RUN",
            "metric": "", "value": "", "accuracy_bootstrap_ci_low": "",
            "accuracy_bootstrap_ci_high": "", "analytical_chance": "",
            "permutation_mean": "", "permutation_p_value": "", "two_sided_advantage": "",
            "symbolic_feature_equality": "", "status": "NOT_TESTED_NO_CANONICAL_LONG_HORIZON_WORKLOAD",
        })
    with (output / "security_falsification_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader(); writer.writerows(results)
    (output / "summary.json").write_text(json.dumps({
        "episodes": len(records), "independent_repetitions": 6,
        "exact_structural_size_feature_equality": len({tuple(row["features"]) for row in records}) == 1,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
