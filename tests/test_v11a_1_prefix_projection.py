from __future__ import annotations

import copy
import unittest

from v11_4.profile import selected_profile
from v11a_confirmatory.projection import (
    CONNECTION_HOPS,
    PER_ROUND_SEQUENCE_FIELDS,
    PREFIX_ROUNDS,
    structural_prefix,
    structural_projection,
)


def synthetic_trace(*, difference_after_round: int | None = None) -> dict:
    profile = selected_profile(10, 3000)
    events = []
    for round_number in range(1, profile.total_rounds + 1):
        events.append(
            {
                "profile_id": (
                    "PUBLIC-DIFFERENCE"
                    if difference_after_round is not None and round_number > difference_after_round
                    else profile.profile_id
                ),
                "session": 1,
                "round": round_number,
                "request_length": 1079,
                "response_length": 800,
                "relay_client_connection_id": "client-0" if round_number <= 100 else "client-1",
                "relay_gateway_connection_id": "gateway-0" if round_number <= 100 else "gateway-1",
                "relay_endpoint": "LOCAL_RELAY",
                "gateway_endpoint": "LOCAL_GATEWAY",
                "ohttp_key_id": 7,
                "kem_id": 32,
                "kdf_id": 1,
                "aead_id": 1,
                "config_epoch": 3,
                "client_http_version": "HTTP/2.0",
                "gateway_http_version": "HTTP/2.0",
                "request_observed_ns": round_number,
                "response_observed_ns": round_number + 1,
            }
        )
    return {"profile_id": profile.profile_id, "public_relay_events": events}


class V11A1PrefixProjectionTests(unittest.TestCase):
    def test_every_sequence_is_a_true_prefix_and_full_horizon_is_identical(self):
        profile = selected_profile(10, 3000)
        full = structural_projection(synthetic_trace(), profile)
        for horizon in PREFIX_ROUNDS:
            prefix = structural_prefix(full, horizon)
            self.assertEqual(prefix["round_count"], horizon)
            for field in PER_ROUND_SEQUENCE_FIELDS:
                self.assertEqual(len(prefix[field]), horizon, field)
                self.assertEqual(prefix[field], full[field][:horizon], field)
            for hop in CONNECTION_HOPS:
                aliases = prefix["connection_reuse_pattern"][hop]
                self.assertEqual(len(aliases), horizon)
                self.assertEqual(prefix["connection_count"][hop], len(set(aliases)))
            self.assertEqual(prefix["session_count"], full["session_count"])
            self.assertEqual(prefix["connection_policy"], full["connection_policy"])
            self.assertEqual(
                prefix["scheduled_public_lifetime_ns"],
                full["scheduled_public_lifetime_ns"],
            )
        self.assertEqual(structural_prefix(full, 356), full)

    def test_connection_count_uses_only_prefix_and_future_difference_is_absent(self):
        profile = selected_profile(10, 3000)
        baseline = structural_projection(synthetic_trace(), profile)
        changed = structural_projection(synthetic_trace(difference_after_round=150), profile)

        for horizon in (50, 100):
            prefix = structural_prefix(baseline, horizon)
            self.assertEqual(prefix["connection_count"], {"relay_client": 1, "relay_gateway": 1})
        later = structural_prefix(baseline, 200)
        self.assertEqual(later["connection_count"], {"relay_client": 2, "relay_gateway": 2})

        self.assertEqual(structural_prefix(baseline, 100), structural_prefix(changed, 100))
        self.assertNotEqual(structural_prefix(baseline, 200), structural_prefix(changed, 200))

    def test_prefix_does_not_mutate_full_projection(self):
        profile = selected_profile(10, 3000)
        full = structural_projection(synthetic_trace(), profile)
        snapshot = copy.deepcopy(full)
        structural_prefix(full, 50)
        self.assertEqual(full, snapshot)


if __name__ == "__main__":
    unittest.main()
