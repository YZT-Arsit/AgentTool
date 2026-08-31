from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RELAY_PRIVATE_KEYS = frozenset(
    {
        "operation_id",
        "logical_action_name",
        "agent_id",
        "route_handle",
        "private_route_alias",
        "result_readiness",
        "provider_diagnostics",
        "scheduler_incidents",
    }
)
REGISTRY_PRIVATE_KEYS = frozenset(
    {
        "operation_id",
        "private_index",
        "private_class",
        "logical_agent_identity",
        "route_handle",
        "real",
        "dummy",
    }
)


def _relative(values: Sequence[int], origin: int) -> list[int]:
    return [int(value) - origin for value in values]


def _gaps(values: Sequence[int]) -> list[int]:
    return [int(right) - int(left) for left, right in zip(values, values[1:])]


def _assert_no_keys(value: Any, forbidden: frozenset[str]) -> None:
    if isinstance(value, Mapping):
        overlap = set(value) & forbidden
        if overlap:
            raise AssertionError(f"attacker projection contains private fields: {sorted(overlap)}")
        for item in value.values():
            _assert_no_keys(item, forbidden)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_keys(item, forbidden)


def relay_timing_projection(trace: Mapping[str, Any]) -> dict[str, Any]:
    events = sorted(
        (dict(item) for item in trace.get("public_relay_events", [])),
        key=lambda item: (int(item["session"]), int(item["round"])),
    )
    if not events:
        raise ValueError("Relay timing projection requires public events")
    requests = [int(item["request_observed_ns"]) for item in events]
    responses = [int(item["response_observed_ns"]) for item in events]
    origin = min(requests)
    projection = {
        "observer": "RELAY",
        "profile_id": str(events[0]["profile_id"]),
        "public_session_ids": [int(item["session"]) for item in events],
        "authenticated_slot_order": [int(item["round"]) for item in events],
        "session_relative_request_ns": _relative(requests, origin),
        "session_relative_response_ns": _relative(responses, origin),
        "request_inter_arrival_ns": _gaps(requests),
        "response_inter_arrival_ns": _gaps(responses),
        "request_response_ns": [response - request for request, response in zip(requests, responses)],
        "total_session_span_ns": max(responses) - origin,
        "request_bytes": [int(item["request_length"]) for item in events],
        "response_bytes": [int(item["response_length"]) for item in events],
        "relay_endpoint_classes": [str(item["relay_endpoint"]) for item in events],
        "gateway_endpoint_classes": [str(item["gateway_endpoint"]) for item in events],
        "client_http_versions": [str(item.get("client_http_version", "")) for item in events],
        "gateway_http_versions": [str(item.get("gateway_http_version", "")) for item in events],
    }
    _assert_no_keys(projection, RELAY_PRIVATE_KEYS)
    return projection


def load_registry_server_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def registry_timing_projection(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile_id: str,
    pir_period_ms: int,
    opportunities: int,
) -> dict[str, Any]:
    events = sorted((dict(item) for item in rows), key=lambda item: int(item["ordinal"]))
    if len(events) != opportunities:
        raise ValueError(f"Registry trace has {len(events)} queries, expected {opportunities}")
    arrivals = [int(item["request_arrival_ns"]) for item in events]
    ready = [int(item["answer_ready_ns"]) for item in events]
    origin = arrivals[0]
    projection = {
        "observer": "REGISTRY",
        "profile_id": profile_id,
        "public_pir_period_ms": int(pir_period_ms),
        "public_resolution_opportunities": int(opportunities),
        "ordinals": [int(item["ordinal"]) for item in events],
        "session_relative_query_arrival_ns": _relative(arrivals, origin),
        "session_relative_response_ready_ns": _relative(ready, origin),
        "inter_query_gap_ns": _gaps(arrivals),
        "query_response_ns": [response - request for request, response in zip(arrivals, ready)],
        "total_resolution_session_span_ns": ready[-1] - origin,
        "query_bytes": [int(item["query_bytes"]) for item in events],
        "answer_bytes": [int(item["answer_bytes"]) for item in events],
        "query_rows": [int(item["query_rows"]) for item in events],
        "query_cols": [int(item["query_cols"]) for item in events],
        "executors": [str(item["executor"]) for item in events],
        "request_kinds": [str(item["request_kind"]) for item in events],
    }
    _assert_no_keys(projection, REGISTRY_PRIVATE_KEYS)
    return projection


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def _longest_true_run(values: Sequence[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _lag_one_autocorrelation(values: Sequence[float]) -> float:
    if len(values) < 3:
        return 0.0
    mean = statistics.fmean(values)
    denominator = sum((value - mean) ** 2 for value in values)
    if denominator == 0:
        return 0.0
    numerator = sum((left - mean) * (right - mean) for left, right in zip(values, values[1:]))
    return numerator / denominator


def _low_frequency_energy_ratio(values: Sequence[float]) -> float:
    if len(values) < 4:
        return 0.0
    mean = statistics.fmean(values)
    centered = [value - mean for value in values]
    total = sum(value * value for value in centered)
    if total == 0:
        return 0.0
    # Fixed dependency-free DFT bins 1..min(4,n/2).  These summary bins do
    # not inspect private state and are frozen before timing qualification.
    count = min(4, len(centered) // 2)
    energy = 0.0
    for frequency in range(1, count + 1):
        real = sum(value * math.cos(2 * math.pi * frequency * index / len(centered)) for index, value in enumerate(centered))
        imag = sum(value * math.sin(2 * math.pi * frequency * index / len(centered)) for index, value in enumerate(centered))
        energy += (real * real + imag * imag) / len(centered)
    return energy / total


def timing_feature_vector(projection: Mapping[str, Any]) -> list[float]:
    if projection.get("observer") == "RELAY":
        sequences = [
            projection["session_relative_request_ns"],
            projection["session_relative_response_ns"],
            projection["request_inter_arrival_ns"],
            projection["response_inter_arrival_ns"],
            projection["request_response_ns"],
        ]
        total = float(projection["total_session_span_ns"])
    elif projection.get("observer") == "REGISTRY":
        sequences = [
            projection["session_relative_query_arrival_ns"],
            projection["session_relative_response_ready_ns"],
            projection["inter_query_gap_ns"],
            projection["query_response_ns"],
        ]
        total = float(projection["total_resolution_session_span_ns"])
    else:
        raise ValueError("unknown timing observer projection")
    vector: list[float] = []
    for sequence in sequences:
        values = [float(value) for value in sequence]
        vector.extend(values)
        if values:
            mean = statistics.fmean(values)
            late_threshold = mean * 1.5
            late = [value > late_threshold for value in values]
            vector.extend(
                [
                    mean,
                    statistics.pstdev(values),
                    min(values),
                    max(values),
                    _quantile(values, 0.50),
                    _quantile(values, 0.90),
                    _quantile(values, 0.95),
                    _quantile(values, 0.99),
                    float(sum(late)),
                    float(_longest_true_run(late)),
                    _lag_one_autocorrelation(values),
                    _low_frequency_energy_ratio(values),
                ]
            )
        else:
            vector.extend([0.0] * 12)
    vector.append(total)
    return vector
