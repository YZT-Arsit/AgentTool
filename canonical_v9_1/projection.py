from __future__ import annotations

from typing import Any

from .profile import PublicCapacityProfile


def _aliases(values: list[str]) -> tuple[list[str], int]:
    mapping: dict[str, str] = {}
    aliases: list[str] = []
    for value in values:
        if value not in mapping:
            mapping[value] = f"CONNECTION_{len(mapping)}"
        aliases.append(mapping[value])
    return aliases, len(mapping)


def _validated_events(trace: dict[str, Any], profile: PublicCapacityProfile) -> list[dict[str, Any]]:
    profile.validate()
    events = list(trace.get("public_relay_events", []))
    if len(events) != profile.total_rounds:
        raise AssertionError("Relay event count differs from the public round count")
    if [int(event["round"]) for event in events] != list(range(1, profile.total_rounds + 1)):
        raise AssertionError("Relay round order differs from the public schedule")
    return events


def strict_structural_projection(
    trace: dict[str, Any], profile: PublicCapacityProfile
) -> dict[str, Any]:
    """Return the exact STRICT structural equality projection.

    Raw timestamps and ephemeral TCP identifiers are intentionally excluded.
    Connection reuse is preserved by first-seen aliases, so a reconnect remains
    visible without requiring independent runs to reuse literal source ports.
    """

    events = _validated_events(trace, profile)
    client_pattern, client_count = _aliases(
        [str(event["relay_client_connection_id"]) for event in events]
    )
    gateway_pattern, gateway_count = _aliases(
        [str(event["relay_gateway_connection_id"]) for event in events]
    )
    return {
        "profile_id_sequence": [str(event["profile_id"]) for event in events],
        "selected_public_ohttp_key_id": [int(event["ohttp_key_id"]) for event in events],
        "kem": [int(event["kem_id"]) for event in events],
        "kdf": [int(event["kdf_id"]) for event in events],
        "aead": [int(event["aead_id"]) for event in events],
        "config_epoch": [int(event["config_epoch"]) for event in events],
        "relay_endpoint_class": [str(event["relay_endpoint"]) for event in events],
        "gateway_endpoint_class": [str(event["gateway_endpoint"]) for event in events],
        "session_count": profile.session_count,
        "session_association": [1] * len(events),
        "connection_count": {
            "relay_client": client_count,
            "relay_gateway": gateway_count,
        },
        "connection_reuse_pattern": {
            "relay_client": client_pattern,
            "relay_gateway": gateway_pattern,
        },
        "connection_policy": profile.connection_policy,
        "round_count": len(events),
        "round_order": [int(event["round"]) for event in events],
        "request_length_sequence": [int(event["request_length"]) for event in events],
        "response_length_sequence": [int(event["response_length"]) for event in events],
        "scheduled_public_lifetime_ns": profile.scheduled_lifetime_ns,
    }


def strict_size_projection(trace: dict[str, Any], profile: PublicCapacityProfile) -> dict[str, list[int]]:
    events = _validated_events(trace, profile)
    return {
        "request_final_bytes": [int(event["request_length"]) for event in events],
        "response_final_bytes": [int(event["response_length"]) for event in events],
    }


def timing_network_diagnostics(trace: dict[str, Any], profile: PublicCapacityProfile) -> dict[str, Any]:
    """Keep non-claim timing data separate from structural equality."""

    events = _validated_events(trace, profile)
    first_request = int(events[0]["request_observed_ns"])
    last_response = int(events[-1]["response_observed_ns"])
    return {
        "first_request_observed_ns": first_request,
        "last_response_observed_ns": last_response,
        "observed_relay_span_ns": last_response - first_request,
        "scheduled_public_lifetime_ns": profile.scheduled_lifetime_ns,
        "last_observation_minus_scheduled_end_ns": (
            last_response - first_request - profile.scheduled_lifetime_ns
        ),
        "literal_ephemeral_connection_ids_retained_only_in_raw_trace": True,
        "connection_close_timestamp": None,
        "connection_close_slip_status": "NOT_CAPTURED_BY_FROZEN_V9_RUNNER",
        "timing_privacy": "OPEN / NOT_TESTED",
    }
