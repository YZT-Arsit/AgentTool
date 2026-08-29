from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from v11_4.profile import (
    HORIZON_CANDIDATES_MS,
    PERIOD_CANDIDATES_MS,
    horizon_candidate_profiles,
    period_candidate_profiles,
    selected_profile,
)


class V114ProfileTests(unittest.TestCase):
    def test_candidate_sets_and_capacity_formula_are_frozen(self) -> None:
        self.assertEqual(PERIOD_CANDIDATES_MS, (10, 20, 25))
        self.assertEqual(HORIZON_CANDIDATES_MS, (2000, 3000, 4000, 5000, 7500, 10000))
        self.assertEqual([p.round_period_ms for p in period_candidate_profiles()], [10, 20, 25])
        p = selected_profile(10, 3000)
        self.assertEqual(p.admission_rounds, 300)
        self.assertEqual(p.completion_rounds, 5)
        self.assertEqual(p.result_capacity_rounds, 50)
        self.assertEqual(p.total_rounds, 356)
        self.assertEqual(p.scheduled_lifetime_ms, 3560)

    def test_horizon_profiles_use_only_selected_predeclared_period(self) -> None:
        profiles = horizon_candidate_profiles(20)
        self.assertEqual([p.admission_horizon_ms for p in profiles], list(HORIZON_CANDIDATES_MS))
        self.assertTrue(all(p.round_period_ms == 20 for p in profiles))
        with self.assertRaises(ValueError):
            horizon_candidate_profiles(5)

    def test_profile_ids_are_public_and_self_consistent(self) -> None:
        for profile in (*period_candidate_profiles(), *horizon_candidate_profiles(10), selected_profile(10, 2000)):
            self.assertNotIn("agent", profile.profile_id.lower())
            self.assertNotIn("tool", profile.profile_id.lower())
            self.assertEqual(profile.go_plan_fields()["round_period_ms"], profile.round_period_ms)


if __name__ == "__main__":
    unittest.main()
