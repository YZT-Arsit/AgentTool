from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC


SEEDS = (0x15D01, 0x15D02, 0x15D03)
BOOTSTRAP_RESAMPLES = 10_000
PERMUTATION_RESAMPLES = 10_000
FEATURE_VIEWS = ("CONTENT_CRYPTOGRAPHIC", "STRUCTURAL", "TIMING", "ALL_ALLOWED")


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest_bytes(value: str) -> np.ndarray:
    return np.frombuffer(bytes.fromhex(value), dtype=np.uint8).astype(np.float64) / 255.0


def tcp_payload(packet: bytes, linktype: int) -> tuple[int, int, bytes] | None:
    if linktype == 1:
        offset = 14
        if len(packet) < offset or packet[12:14] != b"\x08\x00":
            return None
    elif linktype == 113:
        offset = 16
    elif linktype == 101:
        offset = 0
    elif linktype == 0:
        offset = 4
    else:
        raise ValueError(f"unsupported pcap link type {linktype}")
    if len(packet) < offset + 20 or packet[offset] >> 4 != 4:
        return None
    ihl = (packet[offset] & 15) * 4
    if packet[offset + 9] != 6 or len(packet) < offset + ihl + 20:
        return None
    total = int.from_bytes(packet[offset + 2:offset + 4], "big")
    tcp = offset + ihl
    src = int.from_bytes(packet[tcp:tcp + 2], "big")
    dst = int.from_bytes(packet[tcp + 2:tcp + 4], "big")
    data_offset = (packet[tcp + 12] >> 4) * 4
    end = min(len(packet), offset + total)
    start = tcp + data_offset
    return (src, dst, packet[start:end]) if end > start else None


def extract_pcap_features(pcap: Path, public: list[dict[str, Any]], port: int, cache: Path) -> dict[str, np.ndarray]:
    intervals = sorted(
        ((int(row["apsi"]["wall_start_ns"]), int(row["apsi"]["wall_end_ns"]),
          int(row["observation_ordinal"])) for row in public),
        key=lambda value: value[0],
    )
    n = len(public)
    content = np.zeros((n, 64), dtype=np.float32)
    timing = np.zeros((n, 9), dtype=np.float64)
    with pcap.open("rb") as stream:
        header = stream.read(24)
        if len(header) != 24:
            raise ValueError("truncated pcap header")
        magic = header[:4]
        if magic == b"\xd4\xc3\xb2\xa1": endian, divisor = "<", 1_000
        elif magic == b"\xa1\xb2\xc3\xd4": endian, divisor = ">", 1_000
        elif magic == b"\x4d\x3c\xb2\xa1": endian, divisor = "<", 1
        elif magic == b"\xa1\xb2\x3c\x4d": endian, divisor = ">", 1
        else: raise ValueError("unsupported pcap magic")
        linktype = struct.unpack(endian + "I", header[20:24])[0]
        index = 0
        req_hash = hashlib.sha256(); resp_hash = hashlib.sha256()
        req_bytes = resp_bytes = req_packets = resp_packets = 0
        first_ts = last_ts = previous_ts = None
        gaps: list[float] = []

        def finish() -> None:
            nonlocal req_hash, resp_hash, req_bytes, resp_bytes, req_packets, resp_packets
            nonlocal first_ts, last_ts, previous_ts, gaps
            if index >= len(intervals): return
            ordinal = intervals[index][2]
            content[ordinal, :32] = np.frombuffer(req_hash.digest(), dtype=np.uint8) / 255.0
            content[ordinal, 32:] = np.frombuffer(resp_hash.digest(), dtype=np.uint8) / 255.0
            duration = 0.0 if first_ts is None else (last_ts - first_ts) / 1e6
            timing[ordinal] = [req_bytes, resp_bytes, req_packets, resp_packets, duration,
                               0.0 if not gaps else np.median(gaps),
                               0.0 if not gaps else np.percentile(gaps, 95),
                               0.0 if not gaps else max(gaps),
                               0.0 if first_ts is None else (first_ts - intervals[index][0]) / 1e6]
            req_hash = hashlib.sha256(); resp_hash = hashlib.sha256()
            req_bytes = resp_bytes = req_packets = resp_packets = 0
            first_ts = last_ts = previous_ts = None; gaps = []

        while True:
            record = stream.read(16)
            if not record: break
            if len(record) != 16: raise ValueError("truncated pcap record")
            sec, fraction, incl_len, _orig_len = struct.unpack(endian + "IIII", record)
            packet = stream.read(incl_len)
            if len(packet) != incl_len: raise ValueError("truncated pcap packet")
            ts_ns = sec * 1_000_000_000 + fraction * divisor
            while index < len(intervals) and ts_ns > intervals[index][1] + 1_000_000:
                finish(); index += 1
            if index >= len(intervals): break
            if ts_ns < intervals[index][0] - 1_000_000: continue
            parsed = tcp_payload(packet, linktype)
            if parsed is None: continue
            src, dst, payload = parsed
            if first_ts is None: first_ts = ts_ns
            if previous_ts is not None: gaps.append((ts_ns - previous_ts) / 1e6)
            previous_ts = last_ts = ts_ns
            if dst == port:
                req_hash.update(payload); req_bytes += len(payload); req_packets += 1
            elif src == port:
                resp_hash.update(payload); resp_bytes += len(payload); resp_packets += 1
        while index < len(intervals):
            finish(); index += 1
    if np.any(timing[:, 0] == 0) or np.any(timing[:, 1] == 0):
        missing = np.where((timing[:, 0] == 0) | (timing[:, 1] == 0))[0]
        raise RuntimeError(f"pcap could not be mapped to {len(missing)} APSI observations")
    np.savez_compressed(cache, content=content, timing=timing)
    return {"content": content, "timing": timing}


def candidates(binary: bool) -> list[tuple[str, Any]]:
    # The three seeds apply where tree randomness exists. The other families
    # are deterministic with their frozen solver/settings and are fitted once.
    values: list[tuple[str, Any]] = [
        ("LogisticRegression", make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000))),
        ("HistGradientBoosting", HistGradientBoostingClassifier(max_iter=150, learning_rate=.05, l2_regularization=1.0, early_stopping=False)),
        ("RBF_SVM", make_pipeline(StandardScaler(), SVC(C=1.0, gamma="scale"))),
    ]
    for seed in SEEDS:
        values.append((f"ExtraTrees_seed{seed}", ExtraTreesClassifier(
            n_estimators=200, min_samples_leaf=2, n_jobs=-1, random_state=seed,
        )))
    return values


def scores(model: Any, x: np.ndarray, binary: bool) -> np.ndarray:
    if hasattr(model, "decision_function"):
        value = model.decision_function(x)
    else:
        value = model.predict_proba(x)
        if binary: value = value[:, 1]
    return np.asarray(value)


def group_oof(model: Any, x: np.ndarray, y: np.ndarray, groups: np.ndarray, binary: bool) -> np.ndarray:
    unique = np.unique(groups)
    folds = min(5, len(unique))
    out = np.zeros((len(y),) if binary else (len(y), len(np.unique(y))), dtype=float)
    for train, test in GroupKFold(folds).split(x, y, groups):
        fitted = clone(model).fit(x[train], y[train]); out[test] = scores(fitted, x[test], binary)
    return out


def grouped_binary_ci(y: np.ndarray, prediction: np.ndarray, groups: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    unique = np.unique(groups); by_group = {g: np.flatnonzero(groups == g) for g in unique}
    values = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        chosen = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([by_group[g] for g in chosen])
        if len(np.unique(y[indices])) == 2:
            values.append(roc_auc_score(y[indices], prediction[indices]))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def binary_attack(name: str, view: str, x: np.ndarray, y: np.ndarray, split: np.ndarray,
                  groups: np.ndarray) -> dict[str, Any]:
    train, val, test = split == "TRAIN", split == "VALIDATION", split == "TEST"
    selected = None
    for model_name, model in candidates(True):
        fitted = clone(model).fit(x[train], y[train])
        raw_val_auc = roc_auc_score(y[val], scores(fitted, x[val], True))
        # Model/seed selection is orientation invariant and uses validation
        # only. Score direction is frozen later from grouped TRAIN OOF scores.
        key = (max(raw_val_auc, 1 - raw_val_auc), model_name)
        if selected is None or key > selected[0]:
            selected = (key, model_name, model, raw_val_auc)
    assert selected is not None
    _, model_name, model, raw_val_auc = selected
    oof = group_oof(model, x[train], y[train], groups[train], True)
    train_auc = roc_auc_score(y[train], oof)
    orientation = 1 if train_auc >= .5 else -1
    val_auc = raw_val_auc if orientation == 1 else 1 - raw_val_auc
    development = train | val
    fitted = clone(model).fit(x[development], y[development])
    raw = scores(fitted, x[test], True); oriented = orientation * raw
    raw_auc = roc_auc_score(y[test], raw); auc = roc_auc_score(y[test], oriented)
    rng = np.random.default_rng(SEEDS[0] ^ int(hashlib.sha256(f"{name}|{view}".encode()).hexdigest()[:8], 16))
    low, high = grouped_binary_ci(y[test], oriented, groups[test], rng)
    null = np.empty(PERMUTATION_RESAMPLES)
    for index in range(PERMUTATION_RESAMPLES):
        null[index] = roc_auc_score(rng.permutation(y[test]), oriented)
    p = float((1 + np.sum(null >= auc)) / (PERMUTATION_RESAMPLES + 1))
    return {
        "experiment": name, "feature_view": view, "selected_model": model_name,
        "train_oof_raw_auc": train_auc, "train_orientation": orientation,
        "validation_oriented_auc": val_auc, "test_raw_auc": raw_auc,
        "test_train_oriented_auc": auc,
        "test_orientation_invariant_auc": max(raw_auc, 1 - raw_auc),
        "ci95_low": low, "ci95_high": high, "permutation_p": p,
        "n_train": int(train.sum()), "n_validation": int(val.sum()), "n_test": int(test.sum()),
        "test_groups": int(len(np.unique(groups[test]))),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "permutation_resamples": PERMUTATION_RESAMPLES,
    }


def grouped_multiclass_ci(y: np.ndarray, prediction: np.ndarray, groups: np.ndarray,
                          rng: np.random.Generator) -> tuple[float, float]:
    unique = np.unique(groups); by_group = {g: np.flatnonzero(groups == g) for g in unique}
    values = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        chosen = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([by_group[g] for g in chosen])
        values.append(accuracy_score(y[indices], prediction[indices]))
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def multiclass_attack(name: str, view: str, x: np.ndarray, y: np.ndarray, split: np.ndarray,
                      groups: np.ndarray) -> dict[str, Any]:
    train, val, test = split == "TRAIN", split == "VALIDATION", split == "TEST"
    selected = None
    for model_name, model in candidates(False):
        fitted = clone(model).fit(x[train], y[train])
        val_pred = fitted.predict(x[val]); val_acc = accuracy_score(y[val], val_pred)
        key = (val_acc, model_name)
        if selected is None or key > selected[0]: selected = (key, model_name, model, val_acc)
    assert selected is not None
    _, model_name, model, val_acc = selected
    fitted = clone(model).fit(x[train | val], y[train | val]); pred = fitted.predict(x[test])
    acc = accuracy_score(y[test], pred); macro = f1_score(y[test], pred, average="macro")
    rng = np.random.default_rng(SEEDS[1] ^ int(hashlib.sha256(f"{name}|{view}".encode()).hexdigest()[:8], 16))
    low, high = grouped_multiclass_ci(y[test], pred, groups[test], rng)
    null = np.array([accuracy_score(rng.permutation(y[test]), pred) for _ in range(PERMUTATION_RESAMPLES)])
    p = float((1 + np.sum(null >= acc)) / (PERMUTATION_RESAMPLES + 1))
    return {
        "experiment": name, "feature_view": view, "selected_model": model_name,
        "validation_accuracy": val_acc, "test_accuracy": acc, "test_macro_f1": macro,
        "ci95_low": low, "ci95_high": high, "permutation_p": p,
        "confusion_matrix": confusion_matrix(y[test], pred, labels=sorted(np.unique(y))).tolist(),
        "label_order": sorted(np.unique(y).tolist()),
        "n_train": int(train.sum()), "n_validation": int(val.sum()), "n_test": int(test.sum()),
        "test_groups": int(len(np.unique(groups[test]))),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "permutation_resamples": PERMUTATION_RESAMPLES,
    }


def balanced_cross_pairs(accesses: list[dict[str, Any]], position_left: int,
                         position_right: int, salt: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ("TRAIN", "VALIDATION", "TEST"):
        left = [a for a in accesses if a["split"] == split and a["position"] == position_left]
        right = [a for a in accesses if a["split"] == split and a["position"] == position_right]
        by_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for value in right: by_id[value["agent_id"]].append(value)
        positives = []
        for value in left:
            candidates_ = [r for r in by_id[value["agent_id"]] if r["session_id"] != value["session_id"]]
            if candidates_:
                chosen = candidates_[int(hashlib.sha256(f'{salt}|{value["session_id"]}'.encode()).hexdigest()[:8], 16) % len(candidates_)]
                positives.append((value, chosen))
        rng = random_like(salt, split)
        right_order = list(right); rng.shuffle(right_order)
        negatives = []
        for left_value, right_value in zip(left, right_order):
            if left_value["session_id"] != right_value["session_id"] and left_value["agent_id"] != right_value["agent_id"]:
                negatives.append((left_value, right_value))
            if len(negatives) >= len(positives): break
        count = min(len(positives), len(negatives))
        for label, pairs in ((1, positives[:count]), (0, negatives[:count])):
            for first, second in pairs:
                rows.append({"left": first, "right": second, "label": label, "split": split,
                             "group": f'{first["session_id"]}|{second["session_id"]}'})
    return rows


def random_like(seed: int, label: str):
    import random
    return random.Random(seed ^ int(hashlib.sha256(label.encode()).hexdigest()[:8], 16))


def pair_matrix(pairs: list[dict[str, Any]], view: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = []
    for row in pairs:
        left, right = row["left"][view], row["right"][view]
        x.append(np.concatenate((np.abs(left - right), left * right)))
    return (np.asarray(x), np.asarray([r["label"] for r in pairs]),
            np.asarray([r["split"] for r in pairs]), np.asarray([r["group"] for r in pairs]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12666)
    args = parser.parse_args(); root = args.campaign.resolve(); output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    public = jsonl(root / "PUBLIC_ACCESS_OBSERVATIONS.jsonl")
    private = jsonl(root / "PRIVATE_SESSION_LABELS.jsonl")
    if len(public) != 16_000 or len(private) != 4_000:
        raise RuntimeError("final access campaign denominator is incomplete")
    pcap_cache = output / "APSI_PCAP_FEATURES.npz"
    pcap = extract_pcap_features(root / "apsi_wire.pcap", public, args.port, pcap_cache)
    server = jsonl(root / "simplepir/server_visible_trace.jsonl")
    if len(server) != 16_000: raise RuntimeError("SimplePIR server trace denominator changed")
    by_obs = {int(row["observation_ordinal"]): row for row in public}
    pcap_content, pcap_timing = pcap["content"], pcap["timing"]
    accesses: list[dict[str, Any]] = []
    for session in private:
        base = int(session["collection_ordinal"]) * 4
        for position, agent_id in enumerate(session["agent_ids"]):
            apsi_row, pir_row = by_obs[base + position], by_obs[base + position + 1]
            pir_server = server[base + position + 1]
            content = np.concatenate((
                pcap_content[base + position], digest_bytes(pir_row["simplepir"]["query_sha256"]),
            ))
            structural = np.asarray([
                position, 4, 104, 104, 697972, 1579652, 2, 36388, 37180,
                apsi_row["structural_projection"]["gateway_frame_count"], 1079, 800,
            ], dtype=float)
            timing = np.concatenate((pcap_timing[base + position], np.asarray([
                float(pir_server["answer_ms"]),
                (int(pir_server["answer_ready_ns"]) - int(pir_server["request_arrival_ns"])) / 1e6,
                float(apsi_row["start_lateness_ms"]), float(pir_row["start_lateness_ms"]),
            ])))
            accesses.append({
                "session_id": session["session_id"], "split": session["split"],
                "sequence_class": session["sequence_class"], "position": position,
                "agent_id": int(agent_id), "CONTENT_CRYPTOGRAPHIC": content,
                "STRUCTURAL": structural, "TIMING": timing,
                "ALL_ALLOWED": np.concatenate((content, structural, timing)),
                "POSITIVE_CONTROL": np.asarray([float(agent_id)]),
            })

    session_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for access in accesses: session_map[access["session_id"]].append(access)
    within = []
    for values in session_map.values():
        values.sort(key=lambda row: row["position"])
        within.append({"left": values[0], "right": values[2],
                       "label": int(values[0]["agent_id"] == values[2]["agent_id"]),
                       "split": values[0]["split"], "group": values[0]["session_id"]})
    cross_same = balanced_cross_pairs(accesses, 0, 0, 0xC501)
    cross_shift = balanced_cross_pairs(accesses, 0, 1, 0xC502)
    privacy_results = []
    for name, pairs in (("SAME_AGENT_WITHIN_SESSION", within),
                        ("CROSS_SESSION_SAME_SLOT", cross_same),
                        ("CROSS_SESSION_CROSS_SLOT", cross_shift)):
        for view in FEATURE_VIEWS:
            privacy_results.append(binary_attack(name, view, *pair_matrix(pairs, view)))
        positive_x = np.asarray([[int(row["left"]["agent_id"] == row["right"]["agent_id"])] for row in pairs], dtype=float)
        privacy_results.append(binary_attack(
            name, "UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL", positive_x,
            np.asarray([r["label"] for r in pairs]), np.asarray([r["split"] for r in pairs]),
            np.asarray([r["group"] for r in pairs]),
        ))

    sequence_results = []
    ordered_sessions = sorted(private, key=lambda row: row["session_id"])
    for view in FEATURE_VIEWS:
        matrix = np.asarray([
            np.concatenate([next(a for a in session_map[row["session_id"]] if a["position"] == p)[view]
                            for p in range(3)]) for row in ordered_sessions
        ])
        labels = np.asarray([row["sequence_class"] for row in ordered_sessions])
        splits = np.asarray([row["split"] for row in ordered_sessions])
        groups = np.asarray([row["session_id"] for row in ordered_sessions])
        sequence_results.append(multiclass_attack("FOUR_CLASS_ORDERING_RECURRENCE", view, matrix, labels, splits, groups))
        for binary_name, left_label, right_label in (
            ("RARE_INSERTION_AAA_VS_AAB", "AAA", "AAB"),
            ("RECURRENCE_AAA_VS_ABC", "AAA", "ABC"),
            ("RETURN_PATTERN_ABA_VS_ABC", "ABA", "ABC"),
        ):
            keep = (labels == left_label) | (labels == right_label)
            sequence_results.append(binary_attack(
                binary_name, view, matrix[keep], (labels[keep] == left_label).astype(int),
                splits[keep], groups[keep],
            ))
    equality = []
    for row in ordered_sessions:
        a, b, c = row["agent_ids"]
        equality.append([a == b, a == c, b == c])
    sequence_results.append(multiclass_attack(
        "FOUR_CLASS_ORDERING_RECURRENCE", "UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL",
        np.asarray(equality, dtype=float), np.asarray([r["sequence_class"] for r in ordered_sessions]),
        np.asarray([r["split"] for r in ordered_sessions]), np.asarray([r["session_id"] for r in ordered_sessions]),
    ))

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        keys = sorted({key for row in rows for key in row if key != "confusion_matrix"})
        with path.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader()
            for row in rows: writer.writerow({key: row.get(key) for key in keys})
    write_csv(output / "FINAL_PRIVACY_RESULTS.csv", privacy_results)
    write_csv(output / "FINAL_SEQUENCE_RESULTS.csv", sequence_results)
    (output / "ACCESS_STATISTICAL_SUMMARY.json").write_text(json.dumps({
        "schema": "AgentTool.V15DAccessStatistics/1",
        "feature_contract": {
            "content": "SHA-256 representation of reassembled APSI TCP payload by direction plus SHA-256 representation of the actual SimplePIR query",
            "structural": "fixed message counts/sizes, public slot and fixed Gateway structure",
            "timing": "APSI packet timing and cloud-side SimplePIR answer timing only",
            "all": "content + structural + timing",
            "excluded": ["AgentID", "PIR row", "match result", "real/dummy state", "artifact plaintext", "TEE diagnostics"],
        },
        "privacy": privacy_results, "sequence": sequence_results,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
