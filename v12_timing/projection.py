from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

APPLICATION_RECEIVE_TIMESTAMP = "APPLICATION_RECEIVE_TIMESTAMP"
APPLICATION_SEND_TIMESTAMP = "APPLICATION_SEND_TIMESTAMP"
PUBLIC_WIRE_METADATA = "PUBLIC_WIRE_METADATA"
PUBLIC_CONFIGURATION = "PUBLIC_CONFIGURATION"
DERIVED_FROM_ALLOWED_FIELDS = "DERIVED_FROM_ALLOWED_FIELDS"
INTERNAL_PRIVATE_STATE = "INTERNAL_PRIVATE_STATE"
TIMING_ONLY_VIEW = "TIMING_ONLY_VIEW"

# Explicit output schemas. Inputs are read field-by-field; unknown keys cannot
# flow into a projection.
RELAY_TIMING_ONLY_PROVENANCE = {
    "observer": PUBLIC_CONFIGURATION, "view": PUBLIC_CONFIGURATION,
    "profile_id": PUBLIC_CONFIGURATION,
    "public_session_ids": PUBLIC_WIRE_METADATA, "public_slot_order": PUBLIC_WIRE_METADATA,
    # Historical compatibility name. This classifies the slot header as public
    # wire metadata; it does not assert cryptographic authentication by Relay.
    "authenticated_slot_order": PUBLIC_WIRE_METADATA,
    "session_relative_request_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "request_inter_arrival_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "session_relative_response_send_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "response_inter_arrival_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "request_response_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "total_session_span_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "request_bytes": PUBLIC_WIRE_METADATA, "response_bytes": PUBLIC_WIRE_METADATA,
}
REGISTRY_TIMING_ONLY_PROVENANCE = {
    "observer": PUBLIC_CONFIGURATION, "view": PUBLIC_CONFIGURATION,
    "profile_id": PUBLIC_CONFIGURATION, "public_pir_period_ms": PUBLIC_CONFIGURATION,
    "public_resolution_opportunities": PUBLIC_CONFIGURATION, "ordinals": PUBLIC_WIRE_METADATA,
    "session_relative_query_arrival_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "inter_query_gap_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "total_resolution_session_span_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "session_relative_response_send_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "query_response_ns": DERIVED_FROM_ALLOWED_FIELDS,
    "query_bytes": PUBLIC_WIRE_METADATA, "answer_bytes": PUBLIC_WIRE_METADATA,
    "query_rows": PUBLIC_WIRE_METADATA, "query_cols": PUBLIC_WIRE_METADATA,
}
RELAY_SOURCE_PROVENANCE = {
    "request_observed_ns": APPLICATION_RECEIVE_TIMESTAMP,
    "response_send_ns": APPLICATION_SEND_TIMESTAMP,
    "response_observed_ns": INTERNAL_PRIVATE_STATE,
    "session": PUBLIC_WIRE_METADATA, "round": PUBLIC_WIRE_METADATA,
    "request_length": PUBLIC_WIRE_METADATA, "response_length": PUBLIC_WIRE_METADATA,
    "profile_id": PUBLIC_CONFIGURATION,
}
REGISTRY_SOURCE_PROVENANCE = {
    "request_arrival_ns": APPLICATION_RECEIVE_TIMESTAMP,
    "response_send_ns": APPLICATION_SEND_TIMESTAMP,
    "ordinal": PUBLIC_WIRE_METADATA, "query_bytes": PUBLIC_WIRE_METADATA,
    "answer_bytes": PUBLIC_WIRE_METADATA, "query_rows": PUBLIC_WIRE_METADATA,
    "query_cols": PUBLIC_WIRE_METADATA, "profile_id": PUBLIC_CONFIGURATION,
    "pir_period_ms": PUBLIC_CONFIGURATION, "opportunities": PUBLIC_CONFIGURATION,
    "answer_ready_ns": INTERNAL_PRIVATE_STATE,
}
RELAY_REQUEST_TIMING_KEYS = ("session_relative_request_ns", "request_inter_arrival_ns")
RELAY_RESPONSE_TIMING_KEYS = (
    "session_relative_response_send_ns", "response_inter_arrival_ns", "request_response_ns",
)
REGISTRY_REQUEST_TIMING_KEYS = ("session_relative_query_arrival_ns", "inter_query_gap_ns")
REGISTRY_RESPONSE_TIMING_KEYS = ("session_relative_response_send_ns", "query_response_ns")


def observer_contract() -> dict[str, Any]:
    return {
        "roles": {"REGISTRY": "REGISTRY_APPLICATION_OPERATOR", "RELAY": "RELAY_APPLICATION_OPERATOR"},
        "allowed_provenance": [APPLICATION_RECEIVE_TIMESTAMP, APPLICATION_SEND_TIMESTAMP,
                               PUBLIC_WIRE_METADATA, PUBLIC_CONFIGURATION, DERIVED_FROM_ALLOWED_FIELDS],
        "relay_source_fields": dict(RELAY_SOURCE_PROVENANCE),
        "registry_source_fields": dict(REGISTRY_SOURCE_PROVENANCE),
        "relay_projection_fields": dict(RELAY_TIMING_ONLY_PROVENANCE),
        "registry_projection_fields": dict(REGISTRY_TIMING_ONLY_PROVENANCE),
    }


def validate_projection_schema(projection: Mapping[str, Any]) -> None:
    observer = projection.get("observer")
    if observer == "RELAY":
        schema = RELAY_TIMING_ONLY_PROVENANCE
    elif observer == "REGISTRY":
        schema = REGISTRY_TIMING_ONLY_PROVENANCE
    else:
        raise ValueError("unknown timing observer projection")
    unknown = set(projection) - set(schema)
    if unknown:
        raise AssertionError(f"observer projection contains non-allowlisted fields: {sorted(unknown)}")
    if projection.get("view") != TIMING_ONLY_VIEW:
        raise AssertionError("observer projection is not the timing-only view")


def _relative(values: Sequence[int], origin: int) -> list[int]:
    return [int(value) - origin for value in values]


def _gaps(values: Sequence[int]) -> list[int]:
    return [int(right) - int(left) for left, right in zip(values, values[1:])]


def _strictly_monotonic(values: Sequence[int], name: str) -> None:
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError(f"{name} must be strictly chronological within one session")


def relay_timing_projection(trace: Mapping[str, Any], *, expected_rounds: int | None = None) -> dict[str, Any]:
    source = [dict(item) for item in trace.get("public_relay_events", [])]
    if not source:
        raise ValueError("Relay timing projection requires public events")
    if len({int(item["session"]) for item in source}) != 1:
        raise ValueError("primary Relay timing projection requires exactly one public session")
    events = sorted(source, key=lambda item: int(item["request_observed_ns"]))
    if expected_rounds is not None and len(events) != expected_rounds:
        raise ValueError(f"Relay trace has {len(events)} cells, expected public R={expected_rounds}")
    requests = [int(item["request_observed_ns"]) for item in events]
    _strictly_monotonic(requests, "Relay request timestamps")
    slots = [int(item["round"]) for item in events]
    if slots != list(range(1, len(events) + 1)):
        raise ValueError("Relay public slots do not match chronological one-session order")
    origin = requests[0]
    projection = {
        "observer": "RELAY", "view": TIMING_ONLY_VIEW,
        "profile_id": str(events[0]["profile_id"]),
        "public_session_ids": [int(item["session"]) for item in events],
        "public_slot_order": slots,
        "authenticated_slot_order": slots,
        "session_relative_request_ns": _relative(requests, origin),
        "request_inter_arrival_ns": _gaps(requests),
        "total_session_span_ns": requests[-1] - origin,
        "request_bytes": [int(item["request_length"]) for item in events],
        "response_bytes": [int(item["response_length"]) for item in events],
    }
    send_presence = ["response_send_ns" in item for item in events]
    if any(send_presence) and not all(send_presence):
        raise ValueError("Relay response-send instrumentation is incomplete")
    if all(send_presence):
        sends = [int(item["response_send_ns"]) for item in events]
        _strictly_monotonic(sends, "Relay response-send timestamps")
        if any(send < request for request, send in zip(requests, sends)):
            raise ValueError("Relay response-send timestamp precedes its request")
        projection["session_relative_response_send_ns"] = _relative(sends, origin)
        projection["response_inter_arrival_ns"] = _gaps(sends)
        projection["request_response_ns"] = [send - request for request, send in zip(requests, sends)]
        projection["total_session_span_ns"] = sends[-1] - origin
    validate_projection_schema(projection)
    return projection


def load_registry_server_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def registry_timing_projection(rows: Iterable[Mapping[str, Any]], *, profile_id: str,
                               pir_period_ms: int, opportunities: int) -> dict[str, Any]:
    events = sorted((dict(item) for item in rows), key=lambda item: int(item["ordinal"]))
    if len(events) != opportunities:
        raise ValueError(f"Registry trace has {len(events)} queries, expected public Q={opportunities}")
    ordinals = [int(item["ordinal"]) for item in events]
    if ordinals != list(range(opportunities)):
        raise ValueError("Registry ordinals must be the complete public Q sequence")
    arrivals = [int(item["request_arrival_ns"]) for item in events]
    _strictly_monotonic(arrivals, "Registry request timestamps")
    origin = arrivals[0]
    projection: dict[str, Any] = {
        "observer": "REGISTRY", "view": TIMING_ONLY_VIEW, "profile_id": profile_id,
        "public_pir_period_ms": int(pir_period_ms),
        "public_resolution_opportunities": int(opportunities), "ordinals": ordinals,
        "session_relative_query_arrival_ns": _relative(arrivals, origin),
        "inter_query_gap_ns": _gaps(arrivals),
        "total_resolution_session_span_ns": arrivals[-1] - origin,
        "query_bytes": [int(item["query_bytes"]) for item in events],
        "answer_bytes": [int(item["answer_bytes"]) for item in events],
        "query_rows": [int(item["query_rows"]) for item in events],
        "query_cols": [int(item["query_cols"]) for item in events],
    }
    send_presence = ["response_send_ns" in item for item in events]
    if any(send_presence) and not all(send_presence):
        raise ValueError("Registry response-send instrumentation is incomplete")
    if all(send_presence):
        sends = [int(item["response_send_ns"]) for item in events]
        _strictly_monotonic(sends, "Registry response-send timestamps")
        if any(send < arrival for arrival, send in zip(arrivals, sends)):
            raise ValueError("Registry response-send timestamp precedes request arrival")
        projection["session_relative_response_send_ns"] = _relative(sends, origin)
        projection["query_response_ns"] = [send - arrival for arrival, send in zip(arrivals, sends)]
        projection["total_resolution_session_span_ns"] = sends[-1] - origin
    validate_projection_schema(projection)
    return projection


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


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
    return sum((a - mean) * (b - mean) for a, b in zip(values, values[1:])) / denominator


def _low_frequency_energy_ratio(values: Sequence[float]) -> float:
    if len(values) < 4:
        return 0.0
    mean = statistics.fmean(values)
    centered = [value - mean for value in values]
    total = sum(value * value for value in centered)
    if total == 0:
        return 0.0
    energy = 0.0
    for frequency in range(1, min(4, len(centered) // 2) + 1):
        real = sum(v * math.cos(2 * math.pi * frequency * i / len(centered)) for i, v in enumerate(centered))
        imag = sum(v * math.sin(2 * math.pi * frequency * i / len(centered)) for i, v in enumerate(centered))
        energy += (real * real + imag * imag) / len(centered)
    return energy / total


def expected_raw_timing_widths(observer: str, *, public_r: int, public_q: int,
                               has_registry_send: bool = False,
                               has_relay_send: bool = False) -> tuple[int, ...]:
    if observer == "RELAY":
        return (public_r, public_r - 1) + ((public_r, public_r - 1, public_r) if has_relay_send else ())
    if observer == "REGISTRY":
        return (public_q, public_q - 1) + ((public_q, public_q) if has_registry_send else ())
    raise ValueError("unknown timing observer")


def timing_feature_vector(projection: Mapping[str, Any], *, raw_widths: Sequence[int] | None = None) -> list[float]:
    validate_projection_schema(projection)
    if projection["observer"] == "RELAY":
        keys = RELAY_REQUEST_TIMING_KEYS + tuple(k for k in RELAY_RESPONSE_TIMING_KEYS if k in projection)
        total = float(projection["total_session_span_ns"])
    else:
        keys = REGISTRY_REQUEST_TIMING_KEYS + tuple(k for k in REGISTRY_RESPONSE_TIMING_KEYS if k in projection)
        total = float(projection["total_resolution_session_span_ns"])
    sequences = [projection[key] for key in keys]
    widths = tuple(len(sequence) for sequence in sequences) if raw_widths is None else tuple(raw_widths)
    if len(widths) != len(sequences):
        raise ValueError("raw timing widths do not match the timing-only schema")
    vector: list[float] = []
    for sequence, width in zip(sequences, widths, strict=True):
        values = [float(value) for value in sequence]
        if len(values) != int(width):
            raise ValueError("timing sequence length differs from its public-profile-defined width")
        vector.extend(values)
        if values:
            mean = statistics.fmean(values)
            late = [value > mean * 1.5 for value in values]
            vector.extend([mean, statistics.pstdev(values), min(values), max(values),
                           _quantile(values, .50), _quantile(values, .90),
                           _quantile(values, .95), _quantile(values, .99),
                           float(sum(late)), float(_longest_true_run(late)),
                           _lag_one_autocorrelation(values), _low_frequency_energy_ratio(values)])
        else:
            vector.extend([0.0] * 12)
    vector.append(total)
    return vector
