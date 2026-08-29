from __future__ import annotations

import copy
from typing import Any

from canonical_v9_1.projection import strict_size_projection, strict_structural_projection


PREFIX_ROUNDS = (1, 10, 50, 100, 200, 300, 356)


def authenticated_slot_order(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize by authenticated public session/slot, never by timestamps."""

    events = list(trace["public_relay_events"])
    keys = [(int(item["session"]), int(item["round"])) for item in events]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate authenticated public session/slot")
    return sorted(events, key=lambda item: (int(item["session"]), int(item["round"])))


def structural_projection(trace: dict[str, Any], profile) -> dict[str, Any]:
    normalized = copy.deepcopy(trace)
    normalized["public_relay_events"] = authenticated_slot_order(trace)
    value = strict_structural_projection(normalized, profile)
    forbidden = {
        "request_observed_ns",
        "response_observed_ns",
        "actual_send_ns",
        "actual_receive_ns",
        "launch_slip_ns",
        "release_slip_ns",
    }
    if not set(value).isdisjoint(forbidden):
        raise AssertionError("actual timing field entered structural projection")
    return value


def size_projection(trace: dict[str, Any], profile) -> dict[str, Any]:
    normalized = copy.deepcopy(trace)
    normalized["public_relay_events"] = authenticated_slot_order(trace)
    return strict_size_projection(normalized, profile)


def structural_prefix(projection: dict[str, Any], rounds: int) -> dict[str, Any]:
    if rounds not in PREFIX_ROUNDS:
        raise ValueError("prefix is not in the frozen public prefix set")
    result: dict[str, Any] = {}
    sequence_fields = {
        "relay_endpoint_class",
        "gateway_endpoint_class",
        "session_association",
        "public_session_ids",
        "round_order",
        "client_http_versions",
        "gateway_http_versions",
        "request_length_sequence",
        "response_length_sequence",
    }
    for key, value in projection.items():
        result[key] = value[:rounds] if key in sequence_fields else value
    result["round_count"] = rounds
    return result

