from __future__ import annotations

from copy import deepcopy

from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from canonical_v9_1.profile import strict_h50_profile


def _trace(rounds: int) -> dict:
    return {
        "profile_id": "V11_4-STRICT-ONLINE-H50-H3000-P10",
        "public_relay_events": [
            {
                "profile_id": "V11_4-STRICT-ONLINE-H50-H3000-P10",
                "ohttp_key_id": 7,
                "kem_id": 32,
                "kdf_id": 1,
                "aead_id": 1,
                "config_epoch": 3,
                "relay_endpoint": "LOCAL_RELAY",
                "gateway_endpoint": "LOCAL_GATEWAY",
                "session": 1,
                "round": index + 1,
                "request_length": 1079,
                "response_length": 800,
                "client_http_version": "HTTP/2.0",
                "gateway_http_version": "HTTP/2.0",
                "relay_client_connection_id": "client-1",
                "relay_gateway_connection_id": "gateway-1",
            }
            for index in range(rounds)
        ],
        "client_relay_http_version": "HTTP/2.0",
        "relay_gateway_http_version": "HTTP/2.0",
    }


def test_private_scheduler_diagnostics_do_not_change_public_projections() -> None:
    profile = strict_h50_profile()
    trace = _trace(profile.total_rounds)
    before_structural = strict_structural_projection(trace, profile)
    before_size = strict_size_projection(trace, profile)
    with_private = deepcopy(trace)
    with_private["slot_launches"] = [
        {
            "slot": 22,
            "deadline_ns": 220_000_000,
            "wake_lateness_ns": 33_000_000,
            "scheduler_dispatch_ns": 253_000_000,
        }
    ]
    with_private["scheduler_incidents"] = [
        {
            "slot": 22,
            "before": {"pid": 1, "tid": 2, "cpu": 3},
            "after": {"cgroup_nr_throttled": 9},
        }
    ]
    with_private["scheduler_configuration"] = {
        "implementation": "LINUX_CLOCK_NANOSLEEP_TIMER_ABSTIME",
        "pacer_cpu": 207,
    }
    assert strict_structural_projection(with_private, profile) == before_structural
    assert strict_size_projection(with_private, profile) == before_size
