from __future__ import annotations

import copy

import pytest

from canonical_v9_1 import (
    strict_h50_profile,
    strict_size_projection,
    strict_structural_projection,
    validate_profile_id,
)


def event(round_number: int, client: str = "127.0.0.1:51000", gateway: str = "127.0.0.1:52000->127.0.0.1:53000") -> dict[str, object]:
    return {
        "profile_id": "V9_1-STRICT-H50-P1",
        "round": round_number,
        "request_length": 1079,
        "response_length": 800,
        "relay_client_connection_id": client,
        "relay_gateway_connection_id": gateway,
        "relay_endpoint": "LOCAL_RELAY",
        "gateway_endpoint": "LOCAL_GATEWAY",
        "ohttp_key_id": 7,
        "kem_id": 32,
        "kdf_id": 1,
        "aead_id": 1,
        "config_epoch": 3,
        "request_observed_ns": round_number * 5_000_000,
        "response_observed_ns": round_number * 5_000_000 + 100_000,
    }


def test_one_public_profile_accepts_multiple_private_action_counts() -> None:
    profile = strict_h50_profile()
    baseline = profile.go_plan_fields()
    for count in (1, 5, 10, 25, 50):
        profile.admit(count)
        assert profile.go_plan_fields() == baseline
    with pytest.raises(OverflowError):
        profile.admit(51)


@pytest.mark.parametrize(
    "invalid",
    [
        "V9_1-STRICT-H50-P1-AGENT-17",
        "V9_1-STRICT-H50-P1-LEGAL-AGENT",
        "V9_1-STRICT-H50-P1-TOOL-EMAIL",
        "V9_1-STRICT-H50-P1-PROVIDER-SLOW",
        "V9_1-STRICT-H50-P1-ROUTE-EXTERNAL",
        "V9_1-STRICT-H50-P1-ACTUAL-ACTIONS-14",
        "V9_1-STRICT-H50-P1-REPEATED",
        "V9_1-STRICT-H50-P1-RARE",
        "V9_1-STRICT-H50-P1-FREQUENCY-99-1",
        "V9_1-STRICT-H50-P1-WORKLOAD-TOOL",
        "V9_1-STRICT-H50-P1-ARM-A",
        "V9_1-STRICT-H14-P1",
    ],
)
def test_profile_id_rejects_secret_derived_constructions(invalid: str) -> None:
    with pytest.raises(ValueError):
        validate_profile_id(invalid, 50)


def test_connection_projection_ignores_ephemeral_ids_but_preserves_reuse() -> None:
    profile = strict_h50_profile()
    trace_a = {"public_relay_events": [event(index) for index in range(1, profile.total_rounds + 1)]}
    trace_b = {
        "public_relay_events": [
            event(index, "127.0.0.1:61000", "127.0.0.1:62000->127.0.0.1:63000")
            for index in range(1, profile.total_rounds + 1)
        ]
    }
    assert strict_structural_projection(trace_a, profile) == strict_structural_projection(trace_b, profile)
    assert strict_size_projection(trace_a, profile) == strict_size_projection(trace_b, profile)

    trace_reconnect = copy.deepcopy(trace_b)
    trace_reconnect["public_relay_events"][-1]["relay_client_connection_id"] = "127.0.0.1:61001"
    assert strict_structural_projection(trace_a, profile) != strict_structural_projection(trace_reconnect, profile)


def test_projection_rejects_missing_round() -> None:
    profile = strict_h50_profile()
    trace = {"public_relay_events": [event(index) for index in range(1, profile.total_rounds)]}
    with pytest.raises(AssertionError):
        strict_structural_projection(trace, profile)


def test_projection_observes_actual_relay_profile_id() -> None:
    profile = strict_h50_profile()
    left = {"public_relay_events": [event(index) for index in range(1, profile.total_rounds + 1)]}
    right = copy.deepcopy(left)
    right["public_relay_events"][-1]["profile_id"] = "SECRET-DERIVED-INVALID"
    assert strict_structural_projection(left, profile) != strict_structural_projection(right, profile)
