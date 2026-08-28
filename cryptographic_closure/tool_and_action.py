from __future__ import annotations

import csv
import hashlib
import json
import multiprocessing as mp
import os
import random
import socket
import statistics
import tempfile
import threading
import time
import tracemalloc
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from agent_control_virtualization.ir import AgentCapsule, ControlEvent
from agent_control_virtualization.runtime import AgentControlExecutor, ProtectedEvent


FRAME_BYTES = 1024


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _encrypt_frame(key: bytes, value: dict[str, object]) -> bytes:
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    if len(encoded) > FRAME_BYTES - 28:
        raise ValueError("tool envelope overflow")
    plaintext = encoded + b"\0" * (FRAME_BYTES - 28 - len(encoded))
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, b"COMMON_TOOL_V1")


def _decrypt_frame(key: bytes, value: bytes) -> dict[str, object]:
    if len(value) != FRAME_BYTES:
        raise ValueError("invalid fixed envelope")
    plaintext = AESGCM(key).decrypt(value[:12], value[12:], b"COMMON_TOOL_V1")
    return json.loads(plaintext.rstrip(b"\0"))


def _backend_handler(kind: str):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            payload = self.rfile.read(length)
            if kind == "REMOTE":
                result = hashlib.sha256(b"remote" + payload).hexdigest().encode()
            else:
                value = payload
                for _ in range(3000): value = hashlib.sha256(value).digest()
                result = value.hex().encode()
            self.send_response(200); self.send_header("Content-Length", str(len(result))); self.end_headers()
            self.wfile.write(result)
        def log_message(self, *_args) -> None: pass
    return Handler


def _serve_backend(port: int, kind: str) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), _backend_handler(kind)).serve_forever()


def _egress_handler(remote_port: int):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"]); payload = self.rfile.read(length)
            request = urllib.request.Request(f"http://127.0.0.1:{remote_port}/tool", data=payload, method="POST")
            with urllib.request.urlopen(request, timeout=5) as response: result = response.read()
            self.send_response(200); self.send_header("Content-Length", str(len(result))); self.end_headers()
            self.wfile.write(result)
        def log_message(self, *_args) -> None: pass
    return Handler


def _serve_egress(port: int, remote_port: int) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), _egress_handler(remote_port)).serve_forever()


def _common_handler(key: bytes, egress_port: int, document_dir: str):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            request = _decrypt_frame(key, payload); kind = str(request["kind"])
            if kind == "LOCAL":
                path = Path(document_dir) / "synthetic-document.txt"
                path.write_text("synthetic document\n", encoding="utf-8")
                path.write_text(path.read_text(encoding="utf-8") + "modified\n", encoding="utf-8")
                result = hashlib.sha256(path.read_bytes()).hexdigest()
            elif kind == "REMOTE":
                outbound = urllib.request.Request(f"http://127.0.0.1:{egress_port}/egress",
                                                  data=b"synthetic-remote-request", method="POST")
                with urllib.request.urlopen(outbound, timeout=5) as response: result = response.read().decode()
            elif kind == "CLOUD":
                value = b"synthetic-cloud-compute"
                for _ in range(3000): value = hashlib.sha256(value).digest()
                result = value.hex()
            elif kind == "NOOP":
                # Cover traffic terminates inside the common trusted boundary.
                # It never reaches a concrete Tool or invokes a heavy primitive.
                result = "cover-ack"
            else:
                raise ValueError("unknown tool class")
            response = _encrypt_frame(key, {"ok": True, "result": result})
            self.send_response(200); self.send_header("Content-Length", str(len(response))); self.end_headers()
            self.wfile.write(response)
        def log_message(self, *_args) -> None: pass
    return Handler


def _serve_common(port: int, key: bytes, egress_port: int, document_dir: str) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), _common_handler(key, egress_port, document_dir)).serve_forever()


class ToolBoundary:
    def __init__(self):
        self.remote_port, self.egress_port, self.common_port = _free_port(), _free_port(), _free_port()
        self.key = AESGCM.generate_key(bit_length=128)
        self.temp = tempfile.TemporaryDirectory(prefix="acv-tools-")
        self.processes = [
            mp.Process(target=_serve_backend, args=(self.remote_port, "REMOTE"), daemon=True),
            mp.Process(target=_serve_egress, args=(self.egress_port, self.remote_port), daemon=True),
            mp.Process(target=_serve_common, args=(self.common_port, self.key, self.egress_port, self.temp.name), daemon=True),
        ]

    def __enter__(self):
        for process in self.processes: process.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.common_port), timeout=0.1): return self
            except OSError: time.sleep(0.02)
        raise RuntimeError("common tool service failed to start")

    def __exit__(self, *_args):
        for process in self.processes:
            process.terminate(); process.join(timeout=3)
        self.temp.cleanup()

    def protected_call(self, kind: str) -> tuple[dict[str, object], float]:
        body = _encrypt_frame(self.key, {"kind": kind, "args": "synthetic"})
        started = time.perf_counter_ns()
        request = urllib.request.Request(f"http://127.0.0.1:{self.common_port}/execute", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response: result = response.read()
        elapsed = (time.perf_counter_ns() - started) / 1e6
        decoded = _decrypt_frame(self.key, result)
        return ({"endpoint": "CommonToolExecutor", "request_bytes": len(body),
                 "response_bytes": len(result), "event_count": 1,
                 "operation": "PROTECTED_TOOL_SLOT"}, elapsed)

    def direct_view(self, kind: str) -> dict[str, object]:
        return {"endpoint": {"LOCAL": "local-filesystem", "REMOTE": f"remote:{self.remote_port}",
                             "CLOUD": "cloud-compute-process"}[kind], "operation": kind}


def _working_set_bytes() -> int:
    import ctypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = Counters(); counters.cb = ctypes.sizeof(counters)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                            ctypes.byref(counters), counters.cb)
    return int(counters.WorkingSetSize)


def _multiclass_scores(rows: list[dict[str, object]], fields: list[str], label: str) -> list[dict[str, object]]:
    X = np.array([[float(row[field]) for field in fields] for row in rows])
    y = np.array([str(row[label]) for row in rows])
    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "RandomForest": RandomForestClassifier(n_estimators=80, max_depth=9, random_state=17),
    }
    output: list[dict[str, object]] = []
    splitter = StratifiedShuffleSplit(n_splits=5, test_size=0.3, random_state=71)
    for name, model in models.items():
        accuracy: list[float] = []; f1: list[float] = []
        confusion = np.zeros((len(set(y)), len(set(y))), dtype=int); labels = sorted(set(y))
        for train, test in splitter.split(X, y):
            fitted = clone(model).fit(X[train], y[train]); predicted = fitted.predict(X[test])
            accuracy.append(accuracy_score(y[test], predicted)); f1.append(f1_score(y[test], predicted, average="macro"))
            for actual, guess in zip(y[test], predicted): confusion[labels.index(actual), labels.index(guess)] += 1
        rng = np.random.default_rng(77); permutation: list[float] = []
        for _ in range(20):
            shuffled = rng.permutation(y); train, test = next(splitter.split(X, shuffled))
            fitted = clone(model).fit(X[train], shuffled[train]); permutation.append(accuracy_score(shuffled[test], fitted.predict(X[test])))
        output.append({"model": name, "top1_accuracy": statistics.mean(accuracy),
                       "macro_f1": statistics.mean(f1), "permutation_accuracy": statistics.mean(permutation),
                       "chance": 1/len(set(y)), "confusion_matrix": json.dumps(confusion.tolist()),
                       "labels": json.dumps(labels)})
    return output


def _binary_scores(
    X: np.ndarray,
    y: np.ndarray,
    *,
    seed: int,
) -> list[dict[str, object]]:
    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=8, random_state=seed),
    }
    splitter = StratifiedShuffleSplit(n_splits=10, test_size=0.3, random_state=seed)
    output: list[dict[str, object]] = []
    for name, model in models.items():
        aucs: list[float] = []
        accuracies: list[float] = []
        for train, test in splitter.split(X, y):
            fitted = clone(model).fit(X[train], y[train])
            scores = fitted.predict_proba(X[test])[:, 1]
            aucs.append(roc_auc_score(y[test], scores))
            accuracies.append(balanced_accuracy_score(y[test], fitted.predict(X[test])))
        rng = np.random.default_rng(seed + 1000)
        permutations: list[float] = []
        for _ in range(20):
            shuffled = rng.permutation(y)
            train, test = next(splitter.split(X, shuffled))
            fitted = clone(model).fit(X[train], shuffled[train])
            permutations.append(roc_auc_score(shuffled[test], fitted.predict_proba(X[test])[:, 1]))
        observed = statistics.mean(aucs)
        output.append({
            "model": name,
            "auc": observed,
            "balanced_accuracy": statistics.mean(accuracies),
            "permutation_auc": statistics.mean(permutations),
            "permutation_p": (1 + sum(value >= observed for value in permutations)) / (1 + len(permutations)),
            "chance": 0.5,
        })
    return output


def run_action_type(capsule: AgentCapsule, boundary: ToolBoundary, output: Path) -> list[dict[str, object]]:
    rng = random.Random(882); classes = [kind for kind in ("AGENT", "LLM", "TOOL", "NOOP") for _ in range(200)]
    rng.shuffle(classes); executor = AgentControlExecutor({capsule.logical_agent_id: capsule})
    rows: list[dict[str, object]] = []
    for sample_id, kind in enumerate(classes):
        before_rss = _working_set_bytes(); before_cpu = time.process_time_ns(); before_threads = threading.active_count()
        tracemalloc.start(); started = time.perf_counter_ns()
        if kind == "AGENT": executor.step(capsule.logical_agent_id, 0, ProtectedEvent(ControlEvent.START))
        elif kind == "LLM":
            value = b"representative-shared-model-primitive"
            for _ in range(5000): value = hashlib.sha256(value).digest()
        # Every action class crosses the same real RPC boundary once. Only a
        # real TOOL slot is allowed to dispatch beyond that boundary.
        boundary.protected_call("LOCAL" if kind == "TOOL" else "NOOP")
        current, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        wall = time.perf_counter_ns() - started; cpu = time.process_time_ns() - before_cpu
        rows.append({"sample_id": sample_id, "private_action_type": kind, "executor_code": 1, "event_count": 1,
                     "request_bytes": FRAME_BYTES, "response_bytes": FRAME_BYTES,
                     "wall_ns": wall, "cpu_ns": cpu, "python_peak_bytes": peak,
                     "rss_delta_bytes": _working_set_bytes() - before_rss,
                     "thread_delta": threading.active_count() - before_threads})
    results: list[dict[str, object]] = []
    feature_sets = {
        "STRUCTURAL": ["executor_code", "event_count"], "SIZE": ["request_bytes", "response_bytes"],
        "TIMING": ["wall_ns"], "RESOURCE": ["cpu_ns", "python_peak_bytes", "rss_delta_bytes", "thread_delta"],
        "ALL": ["executor_code", "event_count", "request_bytes", "response_bytes", "wall_ns", "cpu_ns",
                "python_peak_bytes", "rss_delta_bytes", "thread_delta"],
    }
    for feature_set, fields in feature_sets.items():
        for result in _multiclass_scores(rows, fields, "private_action_type"):
            results.append({"feature_set": feature_set, **result})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
    visible_fields = [key for key in rows[0] if not key.startswith("private_")]
    host_path = output.with_name("action_type_host_visible_trace.csv")
    with host_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=visible_fields); writer.writeheader()
        writer.writerows({key: row[key] for key in visible_fields} for row in rows)
    private_path = output.with_name("action_type_private_ground_truth.csv")
    with private_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "private_action_type"]); writer.writeheader()
        writer.writerows({"sample_id": row["sample_id"], "private_action_type": row["private_action_type"]} for row in rows)
    return results


def run_tool_sequences(boundary: ToolBoundary, output: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rng = random.Random(449); rows: list[dict[str, object]] = []
    for episode_number in range(10):
        profiles = {
            "TSEQ0": ["LOCAL"] * 100,
            "TSEQ1": ["REMOTE"] * 100,
            "TSEQ2": ["REMOTE"] * 50 + ["LOCAL"] * 50,
            "TSEQ3": (["LOCAL", "REMOTE", "CLOUD"] * 34)[:100],
            "TSEQ4": (["REMOTE", "LOCAL", "CLOUD"] * 34)[:100],
        }
        rng.shuffle(profiles["TSEQ1"]); profiles["TSEQ1"][rng.randrange(100)] = "LOCAL"
        rng.shuffle(profiles["TSEQ2"])
        for profile, sequence in profiles.items():
            for round_number, kind in enumerate(sequence):
                view, elapsed = boundary.protected_call(kind)
                rows.append({"sample_id": len(rows), "episode": f"{profile}-E{episode_number}", "round": round_number,
                             "private_profile": profile, "private_tool": kind,
                             "endpoint": view["endpoint"], "request_bytes": view["request_bytes"],
                             "response_bytes": view["response_bytes"], "event_count": view["event_count"],
                             "wall_ms": elapsed, "real_tool_ops": 1, "dummy_heavy_ops": 0})
    # Tool-class timing is an individual-round three-way attack. Structural and
    # size equality are recorded symbolically because the endpoint is categorical and identical.
    attack_rows: list[dict[str, object]] = []
    for result in _multiclass_scores(rows, ["wall_ms"], "private_tool"):
        attack_rows.append({"attack": "TOOL_CLASS", "feature_set": "TIMING", **result})
    for feature_set in ("STRUCTURAL", "SIZE"):
        attack_rows.append({"attack": "TOOL_CLASS", "feature_set": feature_set, "model": "SYMBOLIC",
                            "top1_accuracy": 1/3, "macro_f1": 1/3, "permutation_accuracy": 1/3,
                            "chance": 1/3, "confusion_matrix": "EXACT_EQUALITY", "labels": "LOCAL,REMOTE,CLOUD"})

    by_episode: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_episode.setdefault(str(row["episode"]), []).append(row)
    episode_features: dict[str, np.ndarray] = {
        episode: np.array([float(row["wall_ms"]) for row in sorted(values, key=lambda item: int(item["round"]))])
        for episode, values in by_episode.items()
    }
    profile_pairs = {
        "FREQUENCY_TSEQ0_V_TSEQ2": ("TSEQ0", "TSEQ2"),
        "RARE_TSEQ0_V_TSEQ1": ("TSEQ0", "TSEQ1"),
        "TRANSITION_TSEQ3_V_TSEQ4": ("TSEQ3", "TSEQ4"),
    }
    for attack, (left, right) in profile_pairs.items():
        selected = [(name, values) for name, values in episode_features.items()
                    if name.startswith(left + "-") or name.startswith(right + "-")]
        X = np.stack([values for _, values in selected])
        y = np.array([int(name.startswith(right + "-")) for name, _ in selected])
        for result in _binary_scores(X, y, seed=449):
            attack_rows.append({"attack": attack, "feature_set": "TIMING", **result})
        attack_rows.append({"attack": attack, "feature_set": "STRUCTURAL_SIZE", "model": "SYMBOLIC",
                            "auc": 0.5, "balanced_accuracy": 0.5, "permutation_auc": 0.5,
                            "permutation_p": 1.0, "chance": 0.5})

    pair_features: list[list[float]] = []
    pair_labels: list[int] = []
    for values in by_episode.values():
        ordered = sorted(values, key=lambda item: int(item["round"]))
        for first, second in zip(ordered, ordered[1:]):
            pair_features.append([float(first["wall_ms"]), float(second["wall_ms"]),
                                  abs(float(first["wall_ms"]) - float(second["wall_ms"]))])
            pair_labels.append(int(first["private_tool"] == second["private_tool"]))
    for result in _binary_scores(np.asarray(pair_features), np.asarray(pair_labels), seed=991):
        attack_rows.append({"attack": "REPEATED_TARGET_LINKABILITY", "feature_set": "TIMING", **result})
    attack_rows.append({"attack": "REPEATED_TARGET_LINKABILITY", "feature_set": "STRUCTURAL_SIZE",
                        "model": "SYMBOLIC", "auc": 0.5, "balanced_accuracy": 0.5,
                        "permutation_auc": 0.5, "permutation_p": 1.0, "chance": 0.5})
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(dict.fromkeys(key for row in attack_rows for key in row))
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames); writer.writeheader(); writer.writerows(attack_rows)
    visible_fields = [key for key in rows[0] if not key.startswith("private_") and key != "episode"]
    host_path = output.with_name("tool_host_visible_trace.csv")
    with host_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=visible_fields); writer.writeheader()
        writer.writerows({key: row[key] for key in visible_fields} for row in rows)
    private_path = output.with_name("tool_private_ground_truth.csv")
    with private_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "episode", "private_profile", "private_tool"])
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in rows)
    return rows, attack_rows
