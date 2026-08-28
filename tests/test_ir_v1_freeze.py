from __future__ import annotations

import csv
import json
import unittest
from collections import Counter
from pathlib import Path

from corpus_audit.ir_v1_freeze import EXPECTED, IR_V1_FILES, verify_frozen_baseline
from corpus_audit.extractor import run_corpus_audit


ROOT = Path(__file__).resolve().parents[1]


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class IRV1FreezeTests(unittest.TestCase):
    def test_frozen_artifact_hashes(self) -> None:
        self.assertEqual(verify_frozen_baseline(ROOT), IR_V1_FILES)

    def test_exact_baseline_and_membership_are_frozen(self) -> None:
        manifest = json.loads((ROOT / "IR_V1_BASELINE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["baseline_id"], "IR-v1")
        self.assertEqual(manifest["status"], "PERMANENTLY_FROZEN")
        self.assertEqual(manifest["counts"], EXPECTED)
        self.assertEqual(manifest["coverage_display"], "48.39%")
        self.assertEqual(len(rows("CORPUS_MANIFEST.csv")), 314)

    def test_unsupported_decomposition_is_complete_without_relabeling(self) -> None:
        original = [row for row in rows("CORPUS_BEHAVIOR_INSTANCES.csv")
                    if row["disposition"] == "UNSUPPORTED"]
        audit = rows("IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv")
        self.assertEqual(len(original), EXPECTED["unsupported"])
        self.assertEqual(len(audit), len(original))
        original_keys = Counter((row["framework"], row["pinned_commit"], row["relative_path"],
                                 row["line"], row["behavior_kind"], row["detail"])
                                for row in original)
        audit_keys = Counter((row["framework"], row["pinned_commit"], row["relative_path"],
                              row["line"], row["behavior_kind"], row["detail"])
                             for row in audit)
        self.assertEqual(audit_keys, original_keys)
        self.assertTrue(all(row["ir_v1_disposition"] == "UNSUPPORTED" for row in audit))

    def test_every_unsupported_family_is_in_pareto(self) -> None:
        pareto = rows("IR_V1_UNSUPPORTED_PARETO.csv")
        self.assertEqual(len(pareto), 10)
        self.assertEqual(sum(int(row["unsupported_instances"]) for row in pareto), 3812)
        self.assertEqual(int(pareto[-1]["cumulative_instances"]), 3812)
        self.assertEqual(float(pareto[-1]["cumulative_percent"]), 1.0)
        forbidden_projection_terms = {"projected_coverage", "estimated_new_coverage", "hypothetical_coverage"}
        self.assertTrue(forbidden_projection_terms.isdisjoint(pareto[0]))

    def test_file_census_and_inclusion_match_frozen_manifest(self) -> None:
        audit = rows("CORPUS_FILE_INCLUSION_AUDIT.csv")
        manifest = rows("CORPUS_MANIFEST.csv")
        self.assertEqual(len(audit), 1099)
        selected = {(row["framework"], row["relative_path"])
                    for row in audit if row["included_ir_v1"] == "YES"}
        expected = {(row["framework"], row["relative_path"]) for row in manifest}
        self.assertEqual(selected, expected)
        self.assertEqual(len(selected), 314)
        self.assertEqual(sum(row["included_ir_v1"] == "NO" for row in audit), 785)
        self.assertTrue(all(row["exclusion_reason"] for row in audit if row["included_ir_v1"] == "NO"))

    def test_dynamic_continuation_is_separate_and_records_failures(self) -> None:
        continuation = rows("IR_V1_DYNAMIC_FIDELITY_CONTINUATION.csv")
        failures = rows("IR_V1_DYNAMIC_FAILURE_CASES.csv")
        self.assertEqual(len(continuation), 72)
        self.assertEqual(sum(row["equivalent"] == "True" for row in continuation), 54)
        self.assertEqual(len(failures), 18)
        self.assertEqual({row["stratum"] for row in failures}, {"openai_tool"})
        self.assertTrue(all(row["execution_id"].startswith("IRV1-CONT-") for row in continuation))

    def test_all_historical_regeneration_paths_refuse_overwrite(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "permanently frozen"):
            run_corpus_audit(ROOT)


if __name__ == "__main__":
    unittest.main()
