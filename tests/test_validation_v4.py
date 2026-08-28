from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_ir_v1_denominator_and_result_are_unchanged() -> None:
    with (ROOT / "CORPUS_IR_COVERAGE.csv").open(newline="", encoding="utf-8") as handle:
        row = next(item for item in csv.DictReader(handle)
                   if item["framework"] == "ALL" and item["behavior_kind"] == "ALL")
    assert (int(row["total"]), int(row["unsupported"])) == (7386, 3812)
    assert round(float(row["coverage"]) * 100, 2) == 48.39


def test_whole_workflow_coverage_uses_distinct_frozen_corpus_units() -> None:
    rows = list(csv.DictReader((ROOT / "WHOLE_WORKFLOW_EXECUTABLE_COVERAGE_V2.csv").open(
        newline="", encoding="utf-8")))
    assert len(rows) == 151
    assert Counter(row["status"] for row in rows) == {
        "FULLY_EXECUTABLE": 33, "PARTIALLY_EXECUTABLE": 97, "UNSUPPORTED": 21,
    }
    assert {row["corpus_version"] for row in rows} == {"IR-v1-frozen-membership"}


def test_mixed_unproven_decomposition_preserves_all_1904_rows_without_coverage_claim() -> None:
    rows = list(csv.DictReader((ROOT / "MIXED_UNPROVEN_DECOMPOSITION_V2.csv").open(
        newline="", encoding="utf-8")))
    assert len(rows) == 1904
    assert all(row["implemented_and_semantically_tested"] == "NO" for row in rows)
    assert all(row["coverage_gain_claimed"] == "NO" for row in rows)
    assert Counter(row["mixed_subclass"] for row in rows) == {
        "SOURCE_TRACEABLE_BOUNDED": 65, "FRAMEWORK_CONTRACT_BOUNDED": 149,
        "GENUINELY_DYNAMIC": 260, "EXTRACTOR_AMBIGUOUS": 1430,
    }


def test_semantic_holdout_manifest_is_still_frozen_and_outcomes_are_not_rewritten() -> None:
    expected = (ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE_SHA256.txt").read_text().split()[0]
    assert hashlib.sha256((ROOT / "SEMANTIC_HOLDOUT_V2_FREEZE.json").read_bytes()).hexdigest() == expected
    result = json.loads((ROOT / "SEMANTIC_HOLDOUT_V2_RESULTS.json").read_text())
    assert result["execution_policy"] == "RUN_ONCE_NO_TUNING"
    assert (result["cases"], result["semantic_passes"], result["tool_passes"]) == (20, 8, 4)
    assert len(result["failed_case_ids"]) == 12
    development = list(csv.DictReader((ROOT / "SEMANTIC_FIDELITY_V2_DEVELOPMENT_REGRESSION_20260828.csv").open(
        newline="", encoding="utf-8")))
    assert len(development) == 72
    assert all(row["equivalent"] == "True" for row in development)


def test_long_horizon_freeze_is_intact_and_functional_failure_blocks_e2e_claim() -> None:
    expected = (ROOT / "LONG_HORIZON_STRUCTURAL_FREEZE_SHA256.txt").read_text().split()[0]
    assert hashlib.sha256((ROOT / "LONG_HORIZON_STRUCTURAL_FREEZE.json").read_bytes()).hexdigest() == expected
    status = json.loads((ROOT / "LONG_HORIZON_STRUCTURAL_EXECUTION_STATUS.json").read_text())
    assert status["status"] == "COMPLETED_FUNCTIONAL_GATE_FAILED"
    assert status["completed_family_pairs"] == 8
    assert "NOT WHOLE_WORKFLOW E2E" in status["privacy_result"]
    assert status["bypass_attempted"] is False
    audited = json.loads((ROOT / "LONG_HORIZON_AUDITED_SUMMARY.json").read_text())
    assert audited["exact_endpoint_count_order_size_session_equality"] is True
    assert audited["grouped_classifier_auc_all_windows"] == 0.5
    assert audited["functional_gate"] == "FAIL"
    assert audited["delivered_results_per_case"] == 0


def test_tcb_inventory_separates_runtime_from_tooling_and_emulator() -> None:
    rows = list(csv.DictReader((ROOT / "TCB_INVENTORY_V4.csv").open(newline="", encoding="utf-8")))
    assert sum(int(row["approx_code_loc"]) for row in rows if row["runtime_tcb"] == "YES") == 2579
    assert all(row["runtime_tcb"] == "NO" for row in rows if row["group"] in {
        "COMPILER_NOT_RUNTIME_TCB", "CORPUS_AND_EXTRACTION_TOOLING",
        "PROVIDER_EMULATOR_NOT_TCB", "EXPERIMENTAL_ANALYSIS_NOT_TCB",
    })
