from __future__ import annotations

import unittest

from v11_3.profile import CANDIDATE_ADMISSION_ROUNDS, OnlinePublicProfile, candidate_profiles


class V113OnlineProfileTests(unittest.TestCase):
    def test_candidates_are_predeclared_and_capacity_is_mechanical(self) -> None:
        profiles = candidate_profiles()
        self.assertEqual(tuple(profile.admission_rounds for profile in profiles), CANDIDATE_ADMISSION_ROUNDS)
        self.assertEqual([profile.total_rounds for profile in profiles], [136, 161, 211, 261, 361])
        self.assertEqual([profile.admission_horizon_ms for profile in profiles], [375, 500, 750, 1000, 1500])
        self.assertTrue(all(profile.maximum_real_operations == 50 for profile in profiles))

    def test_admission_and_operation_capacity_are_independent(self) -> None:
        profile = candidate_profiles()[0]
        self.assertEqual(profile.maximum_real_operations, 50)
        self.assertEqual(profile.admission_rounds, 75)
        self.assertNotEqual(profile.maximum_real_operations, profile.admission_rounds)

    def test_profile_id_is_mechanically_public_and_consistent(self) -> None:
        with self.assertRaises(ValueError):
            OnlinePublicProfile("V11_3-STRICT-ONLINE-H50-A75-P5-secret-tool", 75).validate()
        with self.assertRaises(ValueError):
            OnlinePublicProfile("V11_3-STRICT-ONLINE-H50-A100-P5", 75).validate()

    def test_frozen_wire_and_suite_fields_cannot_change(self) -> None:
        with self.assertRaises(ValueError):
            OnlinePublicProfile("V11_3-STRICT-ONLINE-H50-A75-P5", 75, request_final_bytes=1080).validate()
        with self.assertRaises(ValueError):
            OnlinePublicProfile("V11_3-STRICT-ONLINE-H50-A75-P5", 75, config_epoch=4).validate()


if __name__ == "__main__":
    unittest.main()
