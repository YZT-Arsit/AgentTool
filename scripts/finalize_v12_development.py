from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "results_v12_development"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(value, encoding="utf-8")


def copy_new(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copyfile(source, destination)


def close_simplepir() -> bool:
    source = DEV / "simplepir_runtime_closure_result_2.json"
    ldd_source = DEV / "simplepir_runtime_ldd.txt"
    value = read_json(source)
    passed = all(
        (
            value.get("status") == "PASS",
            value.get("bridge_sha256")
            == "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b",
            value.get("path_without_go_gcc") is True,
            value.get("agent_id") == 17,
            value.get("fd_before") == value.get("fd_after"),
        )
    )
    result = {
        "schema": "AgentTool.V12SimplePIRRuntimeClosure/1",
        "status": "PASS" if passed else "FAIL",
        "dependency_class": "BUILD_TIME_ONLY_FOR_FROZEN_PREBUILT_BINARY",
        "ambiguous_fallback": False,
        "linux_missing_prebuilt_policy": "FAIL_CLOSED_NO_GO_RUN",
        "evidence": value,
        "evidence_sha256": sha256(source),
        "runtime_dynamic_dependencies": ldd_source.read_text(encoding="utf-8").splitlines(),
        "runtime_dynamic_dependencies_sha256": sha256(ldd_source),
        "selected_v12_cases_executed": 0,
    }
    write_json(ROOT / "V12_SIMPLEPIR_RUNTIME_CLOSURE.json", result)
    return passed


def close_resource_and_rehearsal() -> tuple[bool, bool]:
    stress_path = DEV / "resource_stress_500_decisive_result.json"
    rehearsal_path = DEV / "full_campaign_rehearsal_results_decisive.json"
    stress = read_json(stress_path)
    rehearsal = read_json(rehearsal_path)
    thresholds_path = DEV / "resource_stress_500_decisive_preregistered_thresholds.json"
    thresholds = read_json(thresholds_path)
    stress_pass = all(
        (
            stress.get("status") == "PASS",
            stress.get("units_attempted") == 500,
            not stress.get("unit_failures"),
            stress.get("selected_holdout_cases_executed") == 0,
            thresholds.get("units") == 500,
            thresholds.get("sample_every_units") == 10,
            thresholds.get("final_fd_at_most_initial_plus") == 8,
            thresholds.get("retry") is False,
        )
    )
    evidence_checks = []
    for index in range(1, 6):
        root = DEV / f"campaign_rehearsal_{index}_decisive_evidence"
        records = [json.loads(line) for line in (root / "execution_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        previous = "0" * 64
        chain_ok = True
        for record in records:
            body = dict(record)
            observed = body.pop("record_sha256", "")
            chain_ok &= body.get("previous_record_sha256") == previous
            expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            chain_ok &= observed == expected
            previous = observed
        pairs = [read_json(path) for path in sorted(root.glob("pair_*_verdict.json"))]
        summary = read_json(root / "summary.json")
        completion = read_json(root / "campaign_completion.json")
        evidence_checks.append(
            len(records) == 158
            and chain_ok
            and len(pairs) == 14
            and all(item.get("status") == "PASS" for item in pairs)
            and summary.get("status") == "PASS"
            and completion.get("ledger_records") == 158
            and completion.get("final_ledger_record_sha256") == previous
        )
    rehearsal_pass = all(
        (
            rehearsal.get("passed") == 5,
            rehearsal.get("total") == 5,
            rehearsal.get("selected_holdout_cases_executed") == 0,
            all(item.get("ledger_records") == 158 for item in rehearsal.get("summaries", [])),
            all(item.get("structural_pair_pass") == 14 for item in rehearsal.get("summaries", [])),
            all(evidence_checks),
        )
    )
    result = {
        **rehearsal,
        "resource_stress_status": "PASS" if stress_pass else "FAIL",
        "resource_stress_result_sha256": sha256(stress_path),
        "resource_stress_thresholds_sha256": sha256(thresholds_path),
        "executed_rehearsal_script_sha256": sha256(DEV / "executed_run_v12_resource_and_rehearsal.py"),
        "source_rehearsal_result_sha256": sha256(rehearsal_path),
    }
    write_json(ROOT / "V12_FULL_CAMPAIGN_REHEARSAL_RESULTS.json", result)
    write_text(
        ROOT / "V12_FULL_CAMPAIGN_REHEARSAL_AUDIT.md",
        "# V12 full-campaign rehearsal audit\n\n"
        f"The preregistered one-shot 500-unit resource stress is **{'PASS' if stress_pass else 'FAIL'}**. "
        f"Full 158-unit shape-equivalent DEV rehearsals: **{rehearsal.get('passed', 0)}/5 PASS**. "
        "Each passing rehearsal has 65 native-shaped units, 93 canonical-shaped units, "
        "158 append-only ledger records, a valid hash chain, 14 pair verdicts, a summary, "
        "and a completion anchor. No selected V12 case was loaded or executed. Earlier failed "
        "development attempts remain preserved and are not substituted for this decisive run.\n",
    )
    return stress_pass, rehearsal_pass


def close_pir() -> bool:
    # The first development attempt is retained as a failed harness probe.
    # Only the separately named, post-fix one-shot decisive run is eligible.
    source = DEV / "simplepir_evaluation_decisive"
    copy_new(source / "benchmark.csv", ROOT / "V12_SIMPLEPIR_BENCHMARK.csv")
    privacy = read_json(source / "privacy.json")
    rows = list(csv.DictReader((source / "benchmark.csv").open(encoding="utf-8")))
    passed = all(
        (
            len(rows) == 4,
            {int(row["catalog_records"]) for row in rows} == {64, 256, 1024, 4096},
            all(int(row["queries"]) == 30 and row["correct"].lower() == "true" for row in rows),
            privacy.get("pairs") == 100,
            privacy.get("distinct_queries") == 200,
            privacy.get("correct") is True,
            privacy.get("plaintext_agent_id_field_absent") is True,
            privacy.get("private_index_field_absent") is True,
            privacy.get("fresh_server_query_hashes") is True,
        )
    )
    write_text(
        ROOT / "V12_SIMPLEPIR_PRIVACY_EVIDENCE.md",
        "# V12 SimplePIR privacy development evidence\n\n"
        f"Status: **{'PASS' if passed else 'FAIL'}**. The official frozen SimplePIR bridge "
        "executed 30 authenticated 1024-byte descriptor queries at each of 64, 256, 1024, "
        "and 4096 records. A separate deterministic set of 100 distinct-index pairs (200 "
        "queries) recovered every intended row. Server-visible trace fields contain protocol "
        "shape, query/answer byte counts and randomized query hashes, but no plaintext Agent ID "
        "or private-index field. This is empirical integration evidence, not a replacement for "
        "the construction's cryptographic security argument. The first development harness "
        "attempt failed before its first query because it called a nonexistent convenience API; "
        "that partial directory is retained and is not treated as evidence. The separately named "
        "post-fix decisive run above was executed once.\n",
    )
    return passed


def close_profile_requalification() -> bool:
    corrected_path = DEV / "profile_requalification_result.json"
    original_path = DEV / "profile_requalification_original_result.json"
    corrected = read_json(corrected_path)
    original = read_json(original_path)
    passed = all(
        (
            original.get("status") == "FAIL",
            original.get("gates", {}).get("structural_regression_at_least_12")
            is False,
            corrected.get("status") == "PASS",
            corrected.get("execution_rerun") is False,
            corrected.get("corrected_pairs") == ["CAUSAL_DEPTH"],
            all(corrected.get("gates", {}).values()),
            all(value == 0 for value in corrected.get("counters", {}).values()),
            corrected.get("selected_v12_cases_executed") == 0,
        )
    )
    write_json(
        ROOT / "V12_PROFILE_REQUALIFICATION_AUDIT.json",
        {
            "schema": "AgentTool.V12ProfileRequalificationAudit/1",
            "status": "PASS" if passed else "FAIL",
            "original_one_shot_result_status": original.get("status"),
            "original_one_shot_result_sha256": sha256(original_path),
            "analysis_corrected_result_status": corrected.get("status"),
            "analysis_corrected_result_sha256": sha256(corrected_path),
            "execution_rerun": corrected.get("execution_rerun"),
            "corrected_pairs": corrected.get("corrected_pairs"),
            "analysis_rule": corrected.get("analysis_rule"),
            "gates": corrected.get("gates"),
            "counters": corrected.get("counters"),
            "selected_v12_cases_executed": 0,
        },
    )
    write_text(
        ROOT / "V12_PROFILE_REQUALIFICATION_AUDIT.md",
        "# V12 profile requalification audit\n\n"
        f"Status: **{'PASS' if passed else 'FAIL'}**. The one-shot execution completed "
        "450/450 final-reliability cases, 240/240 mixed-causal cases, depths "
        "10/20/30/50, ten semantic regressions, and twelve structural pairs with "
        "zero dummy-heavy operations, overflow, scheduler misses, or silent losses. "
        "Its original analyzer result remains preserved as FAIL: it accidentally "
        "required sequential causal proof from the predeclared PARALLEL_ACTIONS "
        "control in CAUSAL_DEPTH. A read-only analysis correction reapplied the "
        "pre-existing V11.3 rule (causal proof only for DYNAMIC_SEQUENCE), changing "
        "that one classification. No arm was rerun and no selected V12 case was "
        "loaded or executed.\n",
    )
    return passed


def development_summary(
    *, simplepir: bool, stress: bool, rehearsal: bool, pir: bool, performance: bool
) -> bool:
    requal_path = DEV / "profile_requalification_result.json"
    requal_original_path = DEV / "profile_requalification_original_result.json"
    requal = read_json(requal_path)
    requal_original = read_json(requal_original_path)
    performance_detail = read_json(DEV / "performance_result.json")
    full_pytest_log = DEV / "pytest_full_final_302.txt"
    full_pytest_text = (
        full_pytest_log.read_text(encoding="utf-8", errors="replace")
        if full_pytest_log.is_file()
        else ""
    )
    full_unit_tests = "302 passed" in full_pytest_text and " failed" not in full_pytest_text
    security = all(row["status"] == "PASS" for row in csv.DictReader((ROOT / "V12_SECURITY_NEGATIVE_MATRIX.csv").open(encoding="utf-8")))
    baseline = list(csv.DictReader((ROOT / "V12_BASELINE_PRIVACY_MATRIX.csv").open(encoding="utf-8")))
    ablation = list(csv.DictReader((ROOT / "V12_ABLATION_RESULTS.csv").open(encoding="utf-8")))
    expected_baselines = {
        "B0_DIRECT_NATIVE", "B1_PIR_PLUS_DIRECT_ACTION", "B2_PIR_PLUS_OHTTP_UNSHAPED",
        "B3_PIR_PLUS_OHTTP_PADDED", "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL", "B5_FULL_STRICT",
    }
    baseline_functional = all(
        str(row.get("arm_a_functional", "false")).lower() == "true"
        and str(row.get("arm_b_functional", "false")).lower() == "true"
        and row.get("evidence_class") == "ACTUAL_DEV_EXECUTION_PUBLIC_PROJECTION"
        for row in baseline
    )
    gates = {
        "v11b_immutably_sealed": read_json(ROOT / "V11B_ABORTED_CONFIRMATORY_AUDIT.json").get("v11b_rerun_allowed") is False,
        "simplepir_runtime_dependency_closed": simplepir,
        "resource_stress_500": stress,
        "full_campaign_rehearsals_5_of_5": rehearsal,
        "full_unit_tests": full_unit_tests,
        "profile_requalified": all(
            (
                requal.get("status") == "PASS",
                all(requal.get("gates", {}).values()),
                requal.get("execution_rerun") is False,
                requal.get("original_result_status") == "FAIL",
                requal.get("corrected_pairs") == ["CAUSAL_DEPTH"],
                requal_original.get("status") == "FAIL",
                requal_original.get("gates", {}).get("structural_regression_at_least_12")
                is False,
            )
        ),
        "security_negative_matrix": security,
        "simplepir_privacy_and_benchmark": pir,
        "baseline_b0_b5_complete": (
            len(baseline) == 84
            and {row.get("baseline") for row in baseline} == expected_baselines
            and baseline_functional
        ),
        "ablation_complete": len(ablation) == 6,
        "performance_complete": performance,
        "performance_functional_reliability": (
            performance_detail.get("strict_failures") == 0
        ),
        "results_v12_confirmatory_absent": not (ROOT / "results_v12_confirmatory").exists(),
    }
    passed = all(gates.values())
    baseline_equal = {
        baseline_name: sum(
            str(row.get("full_public_structural_projection_equal", "false")).lower() == "true"
            for row in baseline if row.get("baseline") == baseline_name
        )
        for baseline_name in sorted(expected_baselines)
    }
    security_rows = list(csv.DictReader((ROOT / "V12_SECURITY_NEGATIVE_MATRIX.csv").open(encoding="utf-8")))
    value = {
        "schema": "AgentTool.V12DevelopmentEvaluationSummary/1",
        "status": "PASS" if passed else "FAIL",
        "gates": gates,
        "profile_requalification_sha256": sha256(requal_path),
        "profile_requalification_original_result_sha256": sha256(requal_original_path),
        "profile_requalification_analysis_correction": {
            "execution_rerun": requal.get("execution_rerun"),
            "corrected_pairs": requal.get("corrected_pairs"),
            "rule": requal.get("analysis_rule"),
        },
        "action_corpus_coverage": {"mediated": 894, "partial": 473, "unsupported": 3, "total": 1370},
        "development_semantic_and_causal": {
            "final_reliability": "450/450",
            "mixed_causal_families": "240/240",
            "causal_depths": [10, 20, 30, 50],
            "semantic_regression_gate": requal.get("gates", {}).get("semantic_regression_at_least_10", False),
            "structural_regression_gate": requal.get("gates", {}).get("structural_regression_at_least_12", False),
            "safety_counters": requal.get("counters", {}),
        },
        "full_unit_test_regression": {
            "passed": 299,
            "failed": 3,
            "total": 302,
            "serial_recheck": {
                "passed": 2,
                "failed": 1,
                "reproducible_failure": "test_tool_multi_action_capacity[50]: canonical response final size mismatch",
            },
        },
        "security_negatives": {"passed": sum(row["status"] == "PASS" for row in security_rows), "total": len(security_rows)},
        "baseline_equal_dimensions_out_of_14": baseline_equal,
        "ablations": [row["ablation"] for row in ablation],
        "performance": {
            "rows": performance_detail.get("rows"),
            "baseline_count_cells": performance_detail.get("cells"),
            "repetitions_per_cell": performance_detail.get("repetitions_per_cell"),
            "full_strict_rounds": 356,
            "full_strict_scheduled_lifetime_ms": 3560,
            "full_strict_action_transport_bytes": 668924,
            "full_strict_successful_sessions": performance_detail.get(
                "strict_successful_sessions"
            ),
            "full_strict_failures": performance_detail.get("strict_failures"),
            "full_strict_failure_identities": performance_detail.get(
                "strict_failure_identities", []
            ),
        },
        "source_body_executable_subset": 0,
        "source_body_equivalence_go": False,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "selected_v12_cases_executed": 0,
        "ready_for_holdout_freeze": passed,
    }
    write_json(ROOT / "V12_DEVELOPMENT_EVALUATION_SUMMARY.json", value)
    baseline_text = ", ".join(
        f"{name.split('_')[0]} {count}/14" for name, count in baseline_equal.items()
    )
    write_text(
        ROOT / "V12_DEVELOPMENT_EVALUATION_SUMMARY.md",
        "# V12 development evaluation summary\n\n"
        f"Development/freeze gate: **{'PASS' if passed else 'FAIL'}**. The unchanged V11.4 "
        "profile was requalified with 450/450 final-reliability sessions, 240/240 mixed-causal "
        "sessions, depths 10/20/30/50, and zero safety counters. The security-negative matrix, "
        f"B0-B5 baseline ladder ({baseline_text}), "
        f"six ablations, {len(security_rows)}/{len(security_rows)} security negatives, SimplePIR integration evidence, "
        "the 500-unit resource stress, five full campaign rehearsals, and all 30 performance cells "
        "at 30 attempted repetitions are bound by the machine-readable summary. One of 300 fixed-"
        "transcript performance attempts had a real SESSION_SCHEDULE_FAILURE (355/356 rounds, one "
        "schedule miss); it is retained and was not retried. Successful FULL_STRICT sessions are "
        "verified at 356 rounds, 3560 ms scheduled lifetime, and 668,924 Relay-observed action-"
        "transport bytes.\n\n"
        "The final full local regression run was 299/302, not PASS. Two timeout failures passed "
        "a serial no-change recheck; the 50-action V10-H50 case reproducibly failed with "
        "`canonical response final size mismatch`. The failed run and serial recheck are retained. "
        "This independently keeps the pre-holdout system gate closed.\n\n"
        "The original one-shot requalification analyzer emitted FAIL because it incorrectly "
        "required a sequential causal proof from the predeclared PARALLEL_ACTIONS control in "
        "the CAUSAL_DEPTH pair. That original result remains preserved. A read-only reanalysis "
        "using the pre-existing V11.3 workflow-specific rule corrected this sole false negative; "
        "no qualification arm was rerun.\n\n"
        "Corpus scope remains 894 MEDIATED, 473 PARTIAL, and 3 UNSUPPORTED action sites out of 1,370. "
        "Claim boundaries remain: timing privacy OPEN/NOT TESTED; packet-level timing OPEN; "
        "hardware TEE NOT_TESTED; source-body executable subset 0; source-body equivalence false. "
        "No selected V12 holdout result exists.\n",
    )
    return passed


def main() -> None:
    simplepir = close_simplepir()
    stress, rehearsal = close_resource_and_rehearsal()
    pir = close_pir()
    profile = close_profile_requalification()
    performance_result = read_json(DEV / "performance_result.json")
    performance = all(
        (
            performance_result.get("status")
            in {"PASS", "COMPLETE_WITH_RETAINED_FAILURES"},
            performance_result.get("rows") == 900,
            performance_result.get("cells") == 30,
            performance_result.get("repetitions_per_cell") == 30,
            performance_result.get("strict_sessions") == 300,
            performance_result.get("strict_successful_relay_bytes_verified") is True,
            performance_result.get("strict_failed_unit_retried") is False,
            (ROOT / "V12_PERFORMANCE_RESULTS.csv").is_file(),
            (ROOT / "V12_PERFORMANCE_SUMMARY.md").is_file(),
        )
    )
    ready = development_summary(
        simplepir=simplepir,
        stress=stress,
        rehearsal=rehearsal,
        pir=pir,
        performance=performance,
    )
    if not profile:
        ready = False
    print(json.dumps({"ready_for_holdout_freeze": ready}, sort_keys=True))


if __name__ == "__main__":
    main()
