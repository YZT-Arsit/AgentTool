from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from gateway_v2.runner import V2Profile, run_gateway_v2, stress_sessions


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def analyze_development(output: Path, permutations: int = 2000) -> dict[str, object]:
    truth = {int(row["session"]): row["label"] for row in csv.DictReader(
        (output / "private_ground_truth.csv").open(encoding="utf-8", newline="")
    )}
    traces = _jsonl(output / "host_visible_trace.jsonl")
    slips: dict[str, list[float]] = defaultdict(list)
    session_means: dict[int, float] = {}
    preparation_lag: list[float] = []
    request_slip: list[float] = []
    request_ingress: list[float] = []
    receiver_lag: list[float] = []
    by_session: dict[int, list[float]] = defaultdict(list)
    for row in traces:
        slip = (int(row["gateway_response_send_ns"]) - int(row["gateway_response_scheduled_ns"])) / 1e6
        label = truth[int(row["session"])]
        slips[label].append(slip)
        by_session[int(row["session"])].append(slip)
        preparation_lag.append((int(row["gateway_response_prepared_ns"]) - int(row["gateway_response_cutoff_ns"])) / 1e6)
        request_slip.append((int(row["cloud_request_send_ns"]) - int(row["cloud_request_scheduled_ns"])) / 1e6)
        request_ingress.append((int(row["gateway_request_receive_ns"]) - int(row["cloud_request_send_ns"])) / 1e6)
        receiver_lag.append((int(row["cloud_response_receive_ns"]) - int(row["gateway_response_scheduled_ns"])) / 1e6)
    for session, values in by_session.items():
        session_means[session] = float(np.mean(values))

    rows: list[dict[str, object]] = []
    for label, values in sorted(slips.items()):
        data = np.asarray(values)
        rows.append({
            "label": label,
            "slots": len(data),
            "p50_release_slip_ms": float(np.quantile(data, 0.50)),
            "p95_release_slip_ms": float(np.quantile(data, 0.95)),
            "p99_release_slip_ms": float(np.quantile(data, 0.99)),
            "max_release_slip_ms": float(np.max(data)),
            "mean_release_slip_ms": float(np.mean(data)),
        })
    with (output / "release_slip_by_class.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    labels = np.array([truth[session] for session in sorted(session_means)])
    values = np.array([session_means[session] for session in sorted(session_means)])

    def statistic(candidate: np.ndarray) -> float:
        means = [float(np.mean(values[candidate == label])) for label in sorted(set(candidate))]
        return float(np.var(means))

    observed = statistic(labels)
    rng = np.random.default_rng(20260827)
    null = np.array([statistic(rng.permutation(labels)) for _ in range(permutations)])
    p_value = float((1 + np.sum(null >= observed)) / (permutations + 1))
    status = json.loads((output / "pacer_status.json").read_text(encoding="utf-8"))
    result = {
        "kind": "DEVELOPMENT_ONLY",
        "sessions": len(session_means),
        "slots": len(traces),
        "grouped_label_conditioned_variance": observed,
        "permutation_p_value": p_value,
        "permutations": permutations,
        "preparation_lag_p99_ms": float(np.quantile(preparation_lag, 0.99)),
        "preparation_lag_max_ms": float(np.max(preparation_lag)),
        "reference_timing_platform": status["isolation"]["reference_timing_platform"],
        "affinity_applied": status["isolation"]["affinity_applied"],
        "realtime_applied": status["isolation"]["realtime_applied"],
        "timing_decision_allowed": False,
    }
    def distribution(values: list[float]) -> dict[str, float]:
        data = np.asarray(values)
        return {
            "p50_ms": float(np.quantile(data, 0.50)),
            "p95_ms": float(np.quantile(data, 0.95)),
            "p99_ms": float(np.quantile(data, 0.99)),
            "max_ms": float(np.max(data)),
            "mean_ms": float(np.mean(data)),
        }

    result["request_release_slip"] = distribution(request_slip)
    result["request_ingress"] = distribution(request_ingress)
    result["response_release_slip"] = distribution([
        (int(row["gateway_response_send_ns"]) - int(row["gateway_response_scheduled_ns"])) / 1e6
        for row in traces
    ])
    result["receiver_observed_response_lag"] = distribution(receiver_lag)
    result["preparation_lag"] = distribution(preparation_lag)
    (output / "development_independence.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_development(root: Path, output: Path) -> dict[str, object]:
    sessions, providers = stress_sessions()
    profile = V2Profile(
        name="GATEWAY_V2_DEVELOPMENT_STRESS",
        frame_bytes=1024,
        slots=120,
        sessions=len(sessions),
        request_delta_ns=10_000_000,
        response_delta_ns=10_000_000,
        mask_ns=5_000_000,
        start_delay_ns=500_000_000,
        inter_session_gap_ns=20_000_000,
    )
    run = run_gateway_v2(root, output, profile, sessions, providers)
    analysis = analyze_development(output)
    return {"run": run, "analysis": analysis}
