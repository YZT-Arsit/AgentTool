from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = load_module("v11b0_1_driver_under_test", ROOT / "scripts" / "run_v11b_confirmatory.py")
summarizer = load_module(
    "v11b0_1_summarizer_under_test", ROOT / "scripts" / "summarize_v11b_confirmatory.py"
)


class V11B01HardeningTests(unittest.TestCase):
    def test_lf_crlf_git_binding_is_equivalent_but_semantic_mutation_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "dev@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "DEV"], cwd=repo, check=True)
            (repo / ".gitattributes").write_text("*.txt text\n", encoding="utf-8", newline="\n")
            sample = repo / "sample.txt"
            sample.write_bytes(b"alpha\nbeta\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "frozen"], cwd=repo, check=True)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            blob = subprocess.check_output(["git", "show", f"{commit}:sample.txt"], cwd=repo)
            binding = {
                "path": "sample.txt",
                "authoritative_commit": commit,
                "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
            }
            sample.write_bytes(b"alpha\r\nbeta\r\n")
            self.assertTrue(driver.verify_committed_text_binding(binding, root=repo))
            self.assertEqual(
                driver.lf_canonical_sha256_bytes(b"alpha\nbeta\n"),
                driver.lf_canonical_sha256_bytes(b"alpha\r\nbeta\r\n"),
            )
            sample.write_bytes(b"alpha\r\nchanged\r\n")
            self.assertFalse(driver.verify_committed_text_binding(binding, root=repo))

    def test_simplepir_binary_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "pir_integration" / "simplepir_bridge" / "acv-simplepir-online"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"frozen-binary")
            freeze = {
                "status": "FROZEN_LINUX_BINARY",
                "simplepir_revision": "e9020b03bf2872c75b8954e749e32408b5db87ed",
                "actual_resolver_binary_relative_path": "pir_integration/simplepir_bridge/acv-simplepir-online",
                "binary_sha256": hashlib.sha256(b"frozen-binary").hexdigest(),
            }
            self.assertTrue(driver.verify_simplepir_bridge(freeze, root=root)["passed"])
            binary.write_bytes(b"different-binary")
            self.assertFalse(driver.verify_simplepir_bridge(freeze, root=root)["passed"])

    def test_dirty_external_repo_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "dev@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "DEV"], cwd=repo, check=True)
            (repo / "tracked.txt").write_text("frozen\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "frozen"], cwd=repo, check=True)
            self.assertTrue(driver._git_repo_clean(repo))
            (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            self.assertFalse(driver._git_repo_clean(repo))

    def test_wrong_framework_import_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.py"
            outside.write_text("# wrong install\n", encoding="utf-8")
            provenance = {
                "openai": {
                    "revision": "openai-frozen",
                    "source_root_relative": "external_stage10/openai-agents-python",
                    "import_file_sha256": driver.sha256(outside),
                },
                "microsoft": {
                    "revision": "microsoft-frozen",
                    "source_root_relative": "external_stage9/agent-framework",
                    "import_file_sha256": driver.sha256(outside),
                },
                "simplepir": {
                    "revision": "simplepir-frozen",
                    "source_root_relative": "external_pir/simplepir",
                },
            }
            with (
                mock.patch.object(driver, "_git_head", side_effect=lambda path: {
                    "openai-agents-python": "openai-frozen",
                    "agent-framework": "microsoft-frozen",
                    "simplepir": "simplepir-frozen",
                }[path.name]),
                mock.patch.object(driver, "_git_repo_clean", return_value=True),
                mock.patch.object(
                    driver.importlib,
                    "import_module",
                    return_value=SimpleNamespace(__file__=str(outside)),
                ),
            ):
                result = driver.verify_framework_import_provenance(provenance, root=root)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["openai_import_inside_source"])
            self.assertFalse(result["checks"]["microsoft_import_inside_source"])

    def _functional_fixture(self):
        actions = [SimpleNamespace(operation_id="op-a"), SimpleNamespace(operation_id="op-b")]
        requests = {
            "op-a": {"operation_id": "op-a", "arguments": {"value": 1}},
            "op-b": {"operation_id": "op-b", "arguments": {"value": 2}},
        }
        value = {
            "raw_trace": {
                "session_status": "COMPLETE",
                "admitted": 2,
                "provider_invocations": 2,
                "accepted_operation_ids": ["op-a", "op-b"],
                "results": [{"operation_id": "op-a"}, {"operation_id": "op-b"}],
                "resolved_not_admitted_ids": [],
                "framework_waiter_ids": [],
                "pending_operation_ids": [],
                "dummy_provider_operations": 0,
                "profile_overflow_events": 0,
                "schedule_misses": 0,
                "silent_committed_result_losses": 0,
            },
            "semantic": {
                "projection": {
                    "trajectory": [
                        {
                            "operation_id": operation_id,
                            "provider_visible_logical_request": request,
                        }
                        for operation_id, request in requests.items()
                    ]
                }
            },
        }
        return SimpleNamespace(actions=actions), requests, value

    def test_exact_operation_id_and_provider_request_validation(self):
        spec, requests, value = self._functional_fixture()
        with mock.patch.object(driver, "logical_request", side_effect=lambda case: requests[case.operation_id]):
            self.assertTrue(driver.structural_functional_valid(value, spec))
            value["raw_trace"]["results"] = [
                {"operation_id": "op-a"},
                {"operation_id": "op-a"},
            ]
            self.assertFalse(driver.structural_functional_valid(value, spec))

    def test_missing_and_unexpected_operation_ids_are_rejected(self):
        spec, requests, value = self._functional_fixture()
        with mock.patch.object(driver, "logical_request", side_effect=lambda case: requests[case.operation_id]):
            value["raw_trace"]["accepted_operation_ids"] = ["op-a", "op-unexpected"]
            self.assertFalse(driver.structural_functional_valid(value, spec))
            value["raw_trace"]["accepted_operation_ids"] = ["op-a"]
            self.assertFalse(driver.structural_functional_valid(value, spec))

    def _synthetic_campaign(self, root: Path):
        units = []
        index = 0

        def add(family, target, role):
            nonlocal index
            index += 1
            units.append(
                {
                    "global_execution_index": index,
                    "unit_id": f"DEV-U{index:03d}",
                    "phase": "DEV",
                    "family": family,
                    "target_id": target,
                    "role": role,
                    "retry_allowed": False,
                }
            )

        for family, count in (("S1", 32), ("S2", 12), ("S4", 9)):
            for item in range(count):
                target = f"DEV-{family}-{item:02d}"
                add(family, target, "NATIVE")
                add(family, target, "CANONICAL")
        trajectories = []
        for item in range(12):
            target = f"DEV-S3-{item:02d}"
            depth = 30 if item == 0 else 50 if item == 1 else 2
            trajectories.append(
                {"trajectory_id": target, "depth": depth, "actions": [{}] * depth}
            )
            add("S3", target, "NATIVE")
            add("S3", target, "CANONICAL")
        for pair in range(14):
            add(f"DEV-P{pair:02d}", f"DEV-P{pair:02d}-A", "STRUCTURAL_ARM")
            add(f"DEV-P{pair:02d}", f"DEV-P{pair:02d}-B", "STRUCTURAL_ARM")
        self.assertEqual(index, 158)

        plan_path = root / "plan.json"
        plan_path.write_text(json.dumps({"units": units}), encoding="utf-8")
        trajectory_path = root / "trajectories.json"
        trajectory_path.write_text(json.dumps({"trajectories": trajectories}), encoding="utf-8")
        rules_path = ROOT / "V11B0_1_FINAL_DECISION_RULES.json"
        ledger = driver.AppendOnlyLedger(root / "execution_ledger.jsonl")
        for unit in units:
            directory = root / unit["unit_id"]
            directory.mkdir()
            projection = {"target": unit["target_id"]}
            if unit["family"] == "S3" and unit["role"] == "CANONICAL":
                result = {
                    "semantic": {"projection": projection},
                    "causal_proof": {"passed": True},
                }
            else:
                result = {"projection": projection}
            (directory / "unit_result.json").write_text(json.dumps(result), encoding="utf-8")
            ledger.append({**unit, "status_class": "PASS"})
        for pair in range(14):
            verdict = {
                "pair_id": f"DEV-P{pair:02d}",
                "status": "PASS",
                "full_structural_equal": True,
                "size_equal": True,
                "prefix_equal": {str(value): True for value in (1, 10, 50, 100, 200, 300, 356)},
            }
            (root / f"pair_DEV-P{pair:02d}_verdict.json").write_text(
                json.dumps(verdict), encoding="utf-8"
            )
        return plan_path, rules_path, trajectory_path, ledger

    def test_pure_summarizer_and_158_record_requirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan, rules, trajectories, _ledger = self._synthetic_campaign(root)
            summary = summarizer.summarize_campaign(
                root,
                plan_path=plan,
                rules_path=rules,
                trajectory_manifest_path=trajectories,
            )
            self.assertTrue(summary["confirmatory_software_scope_go"])
            ledger = root / "execution_ledger.jsonl"
            lines = ledger.read_text(encoding="utf-8").splitlines()
            ledger.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            truncated = summarizer.summarize_campaign(
                root,
                plan_path=plan,
                rules_path=rules,
                trajectory_manifest_path=trajectories,
            )
            self.assertFalse(truncated["execution_integrity"]["pass"])
            self.assertFalse(truncated["confirmatory_software_scope_go"])

    def test_campaign_completion_is_exclusive_and_requires_158_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _plan, _rules, _trajectories, ledger = self._synthetic_campaign(root)
            summary = root / "V11B_CONFIRMATORY_SUMMARY.json"
            summary.write_text("{}\n", encoding="utf-8")
            freeze = root / "driver-freeze.json"
            freeze.write_text("{}\n", encoding="utf-8")
            driver.write_campaign_completion(
                root,
                ledger=ledger,
                summary_path=summary,
                plan_path=_plan,
                driver_freeze_path=freeze,
            )
            completion = json.loads((root / "campaign_completion.json").read_text(encoding="utf-8"))
            self.assertEqual(completion["completed_ledger_records"], 158)
            with self.assertRaises(FileExistsError):
                driver.write_campaign_completion(
                    root,
                    ledger=ledger,
                    summary_path=summary,
                    plan_path=_plan,
                    driver_freeze_path=freeze,
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = driver.AppendOnlyLedger(root / "execution_ledger.jsonl")
            ledger.append({"global_execution_index": 1, "unit_id": "DEV-U001"})
            summary = root / "V11B_CONFIRMATORY_SUMMARY.json"
            summary.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(driver.HarnessIntegrityFailure):
                driver.write_campaign_completion(root, ledger=ledger, summary_path=summary)


if __name__ == "__main__":
    unittest.main()
