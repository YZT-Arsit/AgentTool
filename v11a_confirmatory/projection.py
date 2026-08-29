from __future__ import annotations

import copy
from typing import Any

from canonical_v9_1.projection import strict_size_projection, strict_structural_projection


PREFIX_ROUNDS = (1, 10, 50, 100, 200, 300, 356)
PER_ROUND_SEQUENCE_FIELDS = (
    "profile_id_sequence",
    "selected_public_ohttp_key_id",
    "kem",
    "kdf",
    "aead",
    "config_epoch",
    "relay_endpoint_class",
    "gateway_endpoint_class",
    "session_association",
    "public_session_ids",
    "round_order",
    "client_http_versions",
    "gateway_http_versions",
    "request_length_sequence",
    "response_length_sequence",
)
CONNECTION_HOPS = ("relay_client", "relay_gateway")


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

    full_rounds = int(projection["round_count"])
    if not 0 < rounds <= full_rounds:
        raise ValueError("prefix horizon exceeds the structural projection")

    result = copy.deepcopy(projection)
    for key in PER_ROUND_SEQUENCE_FIELDS:
        value = projection.get(key)
        if not isinstance(value, list) or len(value) != full_rounds:
            raise ValueError(f"{key} is not a full per-round sequence")
        result[key] = value[:rounds]

    reuse = projection.get("connection_reuse_pattern")
    if not isinstance(reuse, dict):
        raise ValueError("connection_reuse_pattern is missing")
    prefix_reuse: dict[str, list[str]] = {}
    prefix_counts: dict[str, int] = {}
    for hop in CONNECTION_HOPS:
        aliases = reuse.get(hop)
        if not isinstance(aliases, list) or len(aliases) != full_rounds:
            raise ValueError(f"connection_reuse_pattern.{hop} is not a full per-round sequence")
        prefix_aliases = aliases[:rounds]
        prefix_reuse[hop] = prefix_aliases
        prefix_counts[hop] = len(set(prefix_aliases))
    result["connection_reuse_pattern"] = prefix_reuse
    result["connection_count"] = prefix_counts
    result["round_count"] = rounds
    return result
