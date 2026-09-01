from __future__ import annotations

import unittest

from v12_timing.microsoft_t7_rca import (
    COORDINATES,
    FAILED_IMMUTABLE_IDENTITY,
    build_freeze_manifest,
    diagnostic_schedule,
    diagnostic_spec,
    run_diagnostic,
    validate_freeze_manifest,
)


class MicrosoftT7RCATests(unittest.TestCase):
    def test_frozen_matrix_has_six_coordinates_and_1200_fresh_identities(self) -> None:
        schedule = diagnostic_schedule()
        self.assertEqual(len(schedule), 1200)
        self.assertEqual(len({row.identity for row in schedule}), 1200)
        self.assertNotIn(FAILED_IMMUTABLE_IDENTITY, {row.identity for row in schedule})
        self.assertEqual(tuple(row.coordinate for row in schedule[:6]), COORDINATES)
        self.assertTrue(all(row.identity.startswith("DEV-T7-MS-RCA-") for row in schedule))

    def test_freeze_fails_closed_on_failed_identity_reuse(self) -> None:
        manifest = build_freeze_manifest(
            execution_source_commit="test",
            framework_commit="framework",
            framework_source_hashes={},
            analysis_hashes={},
        )
        validate_freeze_manifest(manifest)
        manifest["failed_identity_reexecuted"] = True
        with self.assertRaises(ValueError):
            validate_freeze_manifest(manifest)

    def test_tool_names_are_repeated_only_for_current_policy(self) -> None:
        unique = run_diagnostic(diagnostic_spec("D5_MIXED_UNIQUE_ROUTED_NAMES", 0))
        repeated = run_diagnostic(diagnostic_spec("D6_MIXED_REPEATED_ROUTED_NAMES", 0))
        self.assertEqual(unique["classification"], "ALL_EXPECTED_OPERATIONS_EXECUTED")
        self.assertEqual(repeated["classification"], "ALL_EXPECTED_OPERATIONS_EXECUTED")
        self.assertTrue(all(name.endswith(tuple("0123456789abcdef")) for name in unique["registered_tool_names"]))
        self.assertEqual(
            repeated["registered_tool_names"],
            ["acv_private_route_000", "acv_private_route_001"],
        )

    def test_actual_adapter_class_zero_and_one_execute_exact_operations(self) -> None:
        for coordinate in ("D1_T7_CLASS0_ADAPTER", "D2_T7_CLASS1_ADAPTER"):
            with self.subTest(coordinate=coordinate):
                result = run_diagnostic(diagnostic_spec(coordinate, 0))
                self.assertEqual(result["classification"], "ALL_EXPECTED_OPERATIONS_EXECUTED")
                self.assertEqual(result["executed_operation_ids"], result["expected_operation_ids"])

    def test_minimal_single_paths_reach_expected_semantic_implementation(self) -> None:
        ordinary = run_diagnostic(diagnostic_spec("D3_ORDINARY_TOOL_ONLY", 0))
        child = run_diagnostic(diagnostic_spec("D4_AGENT_AS_TOOL_ONLY", 0))
        self.assertEqual(ordinary["classification"], "ALL_EXPECTED_OPERATIONS_EXECUTED")
        self.assertEqual(child["classification"], "ALL_EXPECTED_OPERATIONS_EXECUTED")
        self.assertIn("ORDINARY_TOOL_INVOKED", [row["stage"] for row in ordinary["events"]])
        self.assertIn("CHILD_CLIENT_INVOKED", [row["stage"] for row in child["events"]])


if __name__ == "__main__":
    unittest.main()
