import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv-stage10" / "Scripts" / "python.exe"
UPSTREAM = ROOT / "external_stage10" / "openai-agents-python"


class Stage10IndependentRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PYTHON.exists():
            raise unittest.SkipTest("Stage-10 local runtime environment is unavailable")
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        subprocess.run(
            [
                str(PYTHON),
                "-m",
                "stage10_final_validation.runtime2_probe",
                "--output",
                str(cls.output / "native.json"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                str(PYTHON),
                str(ROOT / "scripts" / "run_stage10.py"),
                "--output-dir",
                str(cls.output),
                "--pairs-per-seed",
                "2",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.native = json.loads((cls.output / "native.json").read_text(encoding="utf-8"))
        cls.experiment = json.loads(
            (cls.output / "runtime2_experiment.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_second_runtime_is_unmodified_public_source(self):
        commit = subprocess.run(
            ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(UPSTREAM), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(commit, "a40ae9803e6b7a79faa246293f56adb100d5868b")
        self.assertEqual(status, "")
        self.assertEqual(self.native["semantic_patches"], "none")

    def test_native_private_state_changes_adaptive_trajectory(self):
        present = self.native["host_visible_executions"]["execution_0"]
        absent = self.native["host_visible_executions"]["execution_1"]
        self.assertEqual(present["runtime_invocations"], 1)
        self.assertEqual(absent["runtime_invocations"], 2)
        self.assertEqual(present["interruption_count"], 0)
        self.assertEqual(absent["interruption_count"], 1)
        self.assertNotEqual(present["host_visible_trace"], absent["host_visible_trace"])

    def test_same_task_final_effect_and_effect_count(self):
        self.assertTrue(self.native["same_initial_task"])
        self.assertTrue(self.native["same_final_effect"])
        self.assertTrue(self.native["same_effect_count"])
        self.assertTrue(self.native["same_sanitized_result"])
        self.assertEqual(
            self.native["host_visible_executions"]["execution_0"]["effect_count"], 1
        )
        self.assertEqual(
            self.native["host_visible_executions"]["execution_1"]["effect_count"], 1
        )

    def test_no_private_label_in_host_trace(self):
        traces = [
            self.native["host_visible_executions"]["execution_0"]["host_visible_trace"],
            self.native["host_visible_executions"]["execution_1"]["host_visible_trace"],
        ]
        encoded = json.dumps(traces, sort_keys=True)
        for forbidden in ("private_state", "private_label", "approval_state", "secret"):
            self.assertNotIn(forbidden, encoded)

    def test_ground_truth_is_serialized_separately(self):
        encoded_host = json.dumps(self.native["host_visible_executions"], sort_keys=True)
        self.assertNotIn("private_ground_truth", encoded_host)
        self.assertNotIn("APPROVAL_PRESENT", encoded_host)
        self.assertNotIn("APPROVAL_ABSENT", encoded_host)
        self.assertNotIn("approval_persisted", encoded_host)
        self.assertEqual(
            set(self.native["private_ground_truth"]), {"execution_0", "execution_1"}
        )

    def test_same_stage9_ir_and_normalizer_reused(self):
        self.assertEqual(
            self.experiment["same_ir_core"],
            "stage9_adaptive.ir.build_program('AUTHORIZATION')",
        )
        self.assertEqual(
            self.experiment["same_normalizer"],
            "stage9_adaptive.runtime.AdaptiveNormalizer",
        )
        self.assertEqual(self.experiment["horizon"], 5)

    def test_required_variant_pattern(self):
        summary = {row["variant"]: row for row in self.experiment["summary"]}
        self.assertEqual(summary["B0-NATURAL"]["auc_mean"], 1.0)
        self.assertEqual(summary["B1-PER-ACTION-OBLIVIOUS"]["auc_mean"], 1.0)
        self.assertEqual(summary["B2-BOUNDED-ADAPTIVE-OBLIVIOUS"]["auc_mean"], 0.5)
        self.assertTrue(
            summary["B2-BOUNDED-ADAPTIVE-OBLIVIOUS"][
                "symbolic_class_equality_all_seeds"
            ]
        )

    def test_b2_structure_exactly_equal_per_seed(self):
        with (self.output / "runtime2_symbolic_equality.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        b2 = [
            row
            for row in rows
            if row["variant"] == "B2-BOUNDED-ADAPTIVE-OBLIVIOUS"
        ]
        self.assertEqual(len(b2), 3)
        self.assertTrue(all(row["symbolic_result"] == "EQUAL" for row in b2))

    def test_function_and_effect_equivalence_without_dummy_effects(self):
        self.assertTrue(self.experiment["functional_equivalence"])
        self.assertTrue(self.experiment["effect_equivalence"])
        self.assertEqual(self.experiment["dummy_external_effects"], 0)
        self.assertEqual(self.experiment["b2_oram_accesses"], [15])


if __name__ == "__main__":
    unittest.main()
