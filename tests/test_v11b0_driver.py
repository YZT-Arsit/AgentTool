from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
DRIVER_PATH = ROOT / "scripts" / "run_v11b_confirmatory.py"
SPEC = importlib.util.spec_from_file_location("v11b0_driver_under_test", DRIVER_PATH)
assert SPEC is not None and SPEC.loader is not None
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


class V11B0DriverTests(unittest.TestCase):
    def test_plan_has_exact_frozen_order_and_counts_without_runtime_calls(self):
        with (
            mock.patch.object(driver, "run_native_semantic_case", side_effect=AssertionError("runtime called")),
            mock.patch.object(driver, "run_canonical_semantic_case", side_effect=AssertionError("runtime called")),
            mock.patch.object(driver, "run_native_trajectory_case", side_effect=AssertionError("runtime called")),
            mock.patch.object(driver, "run_canonical_online_trajectory_case", side_effect=AssertionError("runtime called")),
            mock.patch.object(driver, "run_structural_arm", side_effect=AssertionError("runtime called")),
            mock.patch.object(driver, "ExecutionPermit", side_effect=AssertionError("permit instantiated")),
        ):
            plan = driver.build_execution_plan()
        self.assertEqual(plan["unit_count"], 158)
        self.assertEqual(plan["native_units"], 65)
        self.assertEqual(plan["canonical_units"], 93)
        self.assertEqual([item["global_execution_index"] for item in plan["units"]], list(range(1, 159)))
        self.assertEqual(len({item["unit_id"] for item in plan["units"]}), 158)
        self.assertTrue(all(item["retry_allowed"] is False for item in plan["units"]))

        phases = [item["phase"] for item in plan["units"]]
        self.assertLess(max(i for i, value in enumerate(phases) if value == "1_SEMANTIC"), min(i for i, value in enumerate(phases) if value == "2_CAUSAL_TRAJECTORY"))
        self.assertLess(max(i for i, value in enumerate(phases) if value == "2_CAUSAL_TRAJECTORY"), min(i for i, value in enumerate(phases) if value == "3_STRUCTURAL"))

    def test_selected_execution_is_impossible_without_independent_approval(self):
        self.assertFalse(driver.OUTPUT_ROOT.exists())
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            authorization = temporary_path / "authorization.json"
            authorization.write_text(
                json.dumps({"phase": "V11B", "approved": False, "authorized_v11b0_commit": "none"}),
                encoding="utf-8",
            )
            runner = temporary_path / "runner"
            runner.write_bytes(b"not-used")
            with mock.patch.object(driver, "ExecutionPermit", side_effect=AssertionError("permit instantiated")):
                result = driver.run_campaign(authorization.resolve(), runner.resolve())
        self.assertEqual(result, 2)
        self.assertFalse(driver.OUTPUT_ROOT.exists())

    def test_append_only_ledger_hash_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "execution_ledger.jsonl"
            ledger = driver.AppendOnlyLedger(path)
            first = ledger.append({"global_execution_index": 1, "unit_id": "DEV-U1"})
            second = ledger.append({"global_execution_index": 2, "unit_id": "DEV-U2"})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(first["previous_record_sha256"], "0" * 64)
        self.assertEqual(second["previous_record_sha256"], first["record_sha256"])
        for row in rows:
            digest = row.pop("record_sha256")
            self.assertEqual(digest, driver.sha256_bytes(driver.canonical_bytes(row)))

    def test_driver_has_no_selected_case_specific_literal(self):
        source = DRIVER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("V11A-S1-", source)
        self.assertNotIn("V11A-S2-", source)
        self.assertNotIn("V11A-S3-", source)
        self.assertNotIn("V11A-S4-", source)
        self.assertNotIn("V11A-P", source)


if __name__ == "__main__":
    unittest.main()
