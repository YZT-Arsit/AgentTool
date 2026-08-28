from __future__ import annotations

import ast
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import TruncatedSVD


RESULTS = ROOT / "OFFLINE_IR_CLASSIFIER_RESULTS.csv"
DETAIL = ROOT / "results_v5" / "offline_ir_classifier_v1.json"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def source_path(framework: str, relative: str) -> Path:
    base = (ROOT / "external_stage10/openai-agents-python" if framework == "OpenAI Agents SDK"
            else ROOT / "external_stage9/agent-framework")
    return base / relative


def ast_tokens(path: Path, cache: dict[Path, str]) -> str:
    if path in cache:
        return cache[path]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        counts = Counter(type(node).__name__ for node in ast.walk(tree))
        wanted = ("If", "For", "While", "AsyncFor", "Lambda", "Await", "Call",
                  "Assign", "Attribute", "Try", "With", "AsyncWith", "Match")
        value = " ".join(f"AST_{name}_{min(counts[name], 20)}" for name in wanted)
    except (OSError, SyntaxError):
        value = "AST_PARSE_UNAVAILABLE"
    cache[path] = value
    return value


def context(path: Path, line: int, cache: dict[Path, list[str]]) -> str:
    try:
        lines = cache.setdefault(path, path.read_text(encoding="utf-8", errors="replace").splitlines())
        return " ".join(lines[max(0, line - 3):min(len(lines), line + 2)])
    except OSError:
        return "SOURCE_UNAVAILABLE"


def dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    behavior = read(ROOT / "CORPUS_BEHAVIOR_INSTANCES.csv")
    audit = read(ROOT / "IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv")
    negative = {(r["framework"], r["relative_path"], r["line"], r["behavior_kind"]): r
                for r in audit if r["semantic_bucket"] == "ARBITRARY_CALLBACK_OR_RUNTIME"}
    rows = []
    seen = set()
    line_cache: dict[Path, list[str]] = {}
    tree_cache: dict[Path, str] = {}
    for row in behavior:
        key = (row["framework"], row["relative_path"], row["line"], row["behavior_kind"])
        if key in seen:
            continue
        if row["disposition"] in {"COMPILED", "SHARED_PRIMITIVE"}:
            label, basis = 1, row["disposition"]
        elif key in negative:
            label, basis = 0, negative[key]["semantic_bucket"]
        else:
            continue
        seen.add(key)
        path = source_path(row["framework"], row["relative_path"])
        text = " ".join((
            f"FRAMEWORK_{row['framework'].split()[0]}", f"KIND_{row['behavior_kind']}",
            row["detail"], row["reason"], context(path, int(row["line"]), line_cache),
            ast_tokens(path, tree_cache),
        ))
        rows.append((text, label, f"{row['framework']}::{row['relative_path']}",
                     row["framework"], basis))
    return (np.asarray([r[0] for r in rows]), np.asarray([r[1] for r in rows]),
            np.asarray([r[2] for r in rows]), np.asarray([r[3] for r in rows]))


def metric_row(name: str, split: str, seed: int, truth: np.ndarray,
               probability: np.ndarray, train_n: int) -> dict[str, object]:
    prediction = probability >= 0.5
    accepted = probability >= 0.9
    rejected = probability <= 0.1
    decided = accepted | rejected
    final = accepted.astype(int)
    false_accepts = int(((truth == 0) & accepted).sum())
    negatives = int((truth == 0).sum())
    calibration_error = float(np.mean(np.abs(probability - truth)))
    return {
        "model": name, "split": split, "seed": seed, "train_instances": train_n,
        "test_instances": len(truth), "macro_f1_at_0_5": f1_score(truth, prediction, average="macro"),
        "lowerable_precision_at_0_5": precision_score(truth, prediction, zero_division=0),
        "lowerable_recall_at_0_5": recall_score(truth, prediction, zero_division=0),
        "false_accept_rate_at_0_9": false_accepts / negatives if negatives else 0.0,
        "false_accept_count_at_0_9": false_accepts,
        "negative_gold_count": negatives,
        "abstention_rate_0_1_0_9": 1.0 - float(decided.mean()),
        "accepted_rate_at_0_9": float(accepted.mean()),
        "mean_absolute_calibration_error": calibration_error,
        "coverage_change_claimed": "NO",
        "interpretation": "compile-time proposal only; verifier and semantic test still mandatory",
    }


def models(seed: int):
    vectorizer = lambda: TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=12000,
                                         sublinear_tf=True)
    return (
        ("LogisticRegression", make_pipeline(vectorizer(), LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=seed))),
        ("LinearSVMCalibrated", make_pipeline(vectorizer(), CalibratedClassifierCV(
            LinearSVC(class_weight="balanced", random_state=seed), method="sigmoid", cv=3))),
        ("RandomForestSVD", make_pipeline(vectorizer(), TruncatedSVD(n_components=64,
            random_state=seed), RandomForestClassifier(n_estimators=250, class_weight="balanced",
                                                        random_state=seed, n_jobs=-1))),
    )


def run() -> None:
    if RESULTS.exists() or DETAIL.exists():
        raise FileExistsError("V5 classifier artifacts already exist; refusing overwrite")
    text, labels, groups, frameworks = dataset()
    rows = []
    for seed in (510, 511, 512):
        train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.25,
                                             random_state=seed).split(text, labels, groups))
        for name, model in models(seed):
            model.fit(text[train], labels[train])
            rows.append(metric_row(name, "FILE_GROUPED", seed, labels[test],
                                   model.predict_proba(text[test])[:, 1], len(train)))
    for train_framework, test_framework in (
        ("OpenAI Agents SDK", "Microsoft Agent Framework"),
        ("Microsoft Agent Framework", "OpenAI Agents SDK"),
    ):
        train, test = frameworks == train_framework, frameworks == test_framework
        for name, model in models(520):
            model.fit(text[train], labels[train])
            rows.append(metric_row(name, f"CROSS_FRAMEWORK:{train_framework}->{test_framework}",
                                   520, labels[test], model.predict_proba(text[test])[:, 1], int(train.sum())))
    RESULTS.parent.mkdir(exist_ok=True)
    with RESULTS.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    DETAIL.parent.mkdir(exist_ok=True)
    DETAIL.write_text(json.dumps({
        "gold_instances": len(labels), "positive_lowerable": int(labels.sum()),
        "negative_arbitrary_runtime": int((labels == 0).sum()),
        "excluded_uncertain": "all MIXED/UNPROVEN and structured-candidate rows",
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"instances": len(labels), "rows": len(rows),
                      "max_false_accept_rate_at_0_9": max(float(r["false_accept_rate_at_0_9"]) for r in rows)}, indent=2))


if __name__ == "__main__":
    run()
