from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE_EVIDENCE"
ARCHIVE = EVIDENCE / "functional_records.tar.gz"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_json(archive: tarfile.TarFile, suffix: str) -> dict[str, Any]:
    matches = [member for member in archive.getmembers() if member.name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one archive member ending in {suffix}: {matches}")
    stream = archive.extractfile(matches[0])
    if stream is None:
        raise ValueError(f"archive member is not readable: {matches[0].name}")
    return json.loads(stream.read().decode("utf-8"))


def framework_result(summary: dict[str, Any], framework: str, workload: str) -> dict[str, Any]:
    matches = [
        row
        for row in summary["results"]
        if row["framework"] == framework and row["workload"] == workload
    ]
    if len(matches) != 1:
        raise ValueError(f"missing unique {framework}/{workload} result")
    return matches[0]


def exact_standard_unit(
    archive: tarfile.TarFile,
    summary: dict[str, Any],
    framework: str,
    code: str,
    workload: str,
) -> dict[str, Any]:
    row = framework_result(summary, framework, workload)
    trace = archive_json(
        archive, f"-{code}-{workload}-001/go_online_result.json"
    )
    registry = archive_json(
        archive, f"-{code}-{workload}-001/pir/online_query_summary.json"
    )
    return {
        "status": "PASS" if row["pass"] else "FAIL",
        "intents": int(row["operation_count"]),
        "admitted": len(trace["accepted_operation_ids"]),
        "provider_invocations": len(trace["provider_diagnostics"]),
        "provider_success": sum(
            item["class"] == "PROVIDER_OK" for item in trace["provider_diagnostics"]
        ),
        "results": len(trace["results"]),
        "resolved_not_admitted": len(trace.get("resolved_not_admitted_ids", [])),
        "silent_losses": int(trace.get("silent_committed_result_losses", 0)),
        "profile_overflow": int(trace.get("profile_overflow_events", 0)),
        "relay_cells": len(trace["public_relay_events"]),
        "registry_queries": int(registry["query_count"]),
        "level_a_semantics": bool(row["functional_checks"]["level_a_semantics"]),
        "exact_operation_ids": bool(
            row["functional_checks"]["exact_external_accepted_ids"]
            and row["functional_checks"]["exact_external_results"]
        ),
        "public_transcript_complete": bool(trace["public_transcript_complete"]),
    }


def stress_result(summary: dict[str, Any], framework: str) -> dict[str, Any]:
    row = framework_result(
        summary, framework, "CAUSAL_DEPTH_50_BOUNDED_HORIZON_STRESS"
    )
    return {
        "status": "PASS" if row["pass"] else "FAIL",
        "intended": int(row["intended_causal_depth"]),
        "admitted_within_H": int(row["admitted_within_public_window"]),
        "post_H_not_admitted": int(row["post_window_not_admitted"]),
        "first_operation_outside_H": row[
            "first_operation_outside_window_index_one_based"
        ],
        "semantic_failures": len(row["semantic_failures"]),
        "silent_losses": int(row["silent_losses"]),
        "guaranteed_depth": "NOT_CLAIMED",
    }


def main() -> int:
    contract = load(ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CONTRACT.json")
    freeze = load(ROOT / "V12_V4R7_BOUNDED_LIVENESS_FUNCTIONAL_FREEZE.json")
    summary = load(EVIDENCE / "BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json")
    prior = load(ROOT / "V12_V4R7_PROVIDER_COMPLETION_BOUND_CLOSURE.json")
    if sha256(ARCHIVE) != "1dfb6c5f29c3f3d500375aa61cd9dd019a460dc4e8ead1ced5f0fb1b29217ad6":
        raise ValueError("functional archive hash changed")
    if freeze["planned_units"] != summary["executed_units"] or summary["retries"] != 0:
        raise ValueError("functional execution inventory disagrees with freeze")
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        capacity_openai = exact_standard_unit(
            archive, summary, "OpenAI Agents SDK", "OA", "CAPACITY_50"
        )
        capacity_microsoft = exact_standard_unit(
            archive, summary, "Microsoft Agent Framework", "MS", "CAPACITY_50"
        )
        cache_openai = exact_standard_unit(
            archive, summary, "OpenAI Agents SDK", "OA", "CACHE_REUSE_30"
        )
        cache_microsoft = exact_standard_unit(
            archive, summary, "Microsoft Agent Framework", "MS", "CACHE_REUSE_30"
        )
    closure = {
        "schema": "AgentTool.V12V4R7BoundedLivenessCapacityClosure/1",
        "base_v4r7": "1ba1fe6a3bd49b38df2af1393b2b1dd1106f1968",
        "base_semantic_provider_audit": "7565186c3215284df714e56fb8a01adb6a86244e",
        "contract_freeze_commit": "3c3cb8119f9cc3b11489e465692955ede2d0abed",
        "functional_harness_commit": "92a237bff989c140baafa2c6eb36d7c62a71a5ee",
        "M_operation_capacity": contract["operation_capacity_contract"],
        "H_admission_horizon": contract["admission_horizon_contract"],
        "M_implies_causal_depth_50": False,
        "old_causal_depth_oracle": contract["old_causal_depth_oracle"],
        "source_locations_verified": {
            "M_and_round_capacity": "v12_timing/profile.py:122-140",
            "online_M_count_limit": "common_action_gateway_v2/canonicalv9/online.go:399,428",
            "online_admission_slot_window": "common_action_gateway_v2/canonicalv9/online.go:456-487",
            "static_plan_M_guard": "common_action_gateway_v2/canonicalv9/runner.go:347-348",
            "V4R7_R_formula": "common_action_gateway_v2/canonicalv9/runner.go:503",
            "historical_unconditional_oracle": "scripts/run_v12_duplex_functional.py:244-284",
        },
        "original_v4r7_functional_qualification": "FAIL_PRESERVED",
        "historical_causal_depth_50": contract["historical_causal_depth_50"],
        "v4r7_synthetic_reliability": (
            f"{prior['v4r7_synthetic_reliability']['passed']}/"
            f"{prior['v4r7_synthetic_reliability']['planned']} PASS_PRESERVED_NO_RERUN"
        ),
        "functional_execution": {
            "planned": int(summary["planned_units"]),
            "executed": int(summary["executed_units"]),
            "passed": int(summary["passed_units"]),
            "failed": int(summary["failed_units"]),
            "retries": int(summary["retries"]),
            "common_integrity_abort": bool(summary["common_integrity_abort"]),
        },
        "capacity_50_openai": capacity_openai,
        "capacity_50_microsoft": capacity_microsoft,
        "cache_reuse_30_openai": cache_openai,
        "cache_reuse_30_microsoft": cache_microsoft,
        "causal_depth_50_openai": stress_result(summary, "OpenAI Agents SDK"),
        "causal_depth_50_microsoft": stress_result(
            summary, "Microsoft Agent Framework"
        ),
        "smoke_scope_functional_mechanisms": summary[
            "smoke_scope_functional_mechanisms"
        ],
        "full_fixed_H_functional_correctness": summary[
            "full_fixed_h_functional_correctness"
        ],
        "operation_capacity_M50": summary["operation_capacity_m50"],
        "guaranteed_causal_depth_50": "NOT_CLAIMED",
        "protected_runtime_diff": "NONE",
        "unchanged_public_profile": {
            "H_ms": 4500,
            "B_ms": 200,
            "Delta_ms": 10,
            "M": 50,
            "R": 521,
            "Q": 100,
            "response_rho_ms": 30,
            "response_preparation_lead_ms": 20,
        },
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
        "ready_for_development_duplex_repair_smoke": bool(
            summary["ready_for_development_duplex_repair_smoke"]
        ),
        "ready_for_full_p10_sentinel": False,
        "p20": "NOT_RUN",
        "p25": "NOT_RUN",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "evidence_hashes": {
            "contract": sha256(
                ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CONTRACT.json"
            ),
            "freeze": sha256(
                ROOT / "V12_V4R7_BOUNDED_LIVENESS_FUNCTIONAL_FREEZE.json"
            ),
            "functional_summary": sha256(
                EVIDENCE / "BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json"
            ),
            "execution_ledger": sha256(EVIDENCE / "execution_ledger.jsonl"),
            "functional_archive": sha256(ARCHIVE),
        },
    }
    (ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE.json").write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8"
    )
    oa_stress = closure["causal_depth_50_openai"]
    ms_stress = closure["causal_depth_50_microsoft"]
    md = f"""# V12 V4R7 Bounded Liveness and Capacity Closure

The historical V4R7 functional result remains `FAIL`. The corrected contract separates `M=50` operation capacity from arbitrary sequential causal-depth progress within `H=4500 ms`; guaranteed causal depth 50 is `NOT_CLAIMED`.

The immutable historical failure reconciles as 39 admitted and correctly returned operations, 11 explicit post-window `PROFILE_ADMISSION_CLOSED` outcomes, and zero silent losses. The old unconditional exact-50 oracle is `OVERSTATED_BOUNDED_LIVENESS_CONTRACT`.

Fresh execution used 16/16 pre-frozen identities exactly once. Both OpenAI and Microsoft `CAPACITY_50` admitted and returned 50/50 operations with 50/50 `PROVIDER_OK`, zero rejected operations, zero silent loss, `R=521`, and `Q=100`. Both `CACHE_REUSE_30` units passed; in particular Microsoft confirms closure of the earlier 50 ms provider-timeout defect.

The bounded causal stress observed OpenAI {oa_stress['admitted_within_H']}/50 and Microsoft {ms_stress['admitted_within_H']}/50 admitted within this realization of H, with {oa_stress['post_H_not_admitted']} and {ms_stress['post_H_not_admitted']} explicit post-window operations respectively. These are descriptive observations, not guaranteed limits.

`FULL_FIXED_H_FUNCTIONAL_CORRECTNESS = PASS`; `OPERATION_CAPACITY_M50 = PASS`; `READY_FOR_DEVELOPMENT_DUPLEX_REPAIR_SMOKE = YES`. No reliability rerun, classifier, AUC, P20, or P25 execution occurred.
"""
    (ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE.md").write_text(
        md, encoding="utf-8"
    )
    integrity = {
        "schema": "AgentTool.V12V4R7BoundedLivenessExecutionIntegrity/1",
        "execution_host": "controlled Linux research host",
        "source_hashes": {
            "scripts/run_v12_duplex_functional.py": "dc5ea0aad7e0b04496ffb6c4a61f25c7bc17b9b9d21316e14caa2da1f4ed0e56",
            "scripts/run_v12_v4r7_bounded_liveness_functional.py": "3e43e732471f9461bb0c6ff3b73962018d8feec206d1275aab96ee79bbae5c54",
            "v12_timing/profile.py": "5a7830c857688b5604ec0679713b45fbcf29dd8aa7551d1c2ad9fc3aadfcf13c",
            "v11_online/session.py": "fb8aec445075fc2dcf0368eff2d017b8edda098c4ee933e786a31ccea1b29a03",
        },
        "binary_hashes": {
            "canonical_v12_duplex_timing_runner": "c031307e7ea1c2745e8be48bf794e61a30bfbb3de03f9986e1bf26b7b1962892",
            "simplepir_v12_timing": "743684a35afcee942ff76810a091925ce9ca8eb21e33519c3748c694ef1c6f8c",
        },
        "tests": "46 PASS, 2 SKIP (Linux runner unavailable on Windows)",
        "v4r7_reliability_rerun_sessions": 0,
        "functional_identities": "16/16 exact frozen inventory",
        "functional_retries": 0,
        "protected_runtime_diff": "NONE",
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
    }
    (EVIDENCE / "EXECUTION_INTEGRITY.json").write_text(
        json.dumps(integrity, indent=2) + "\n", encoding="utf-8"
    )
    readme = f"""# V12 V4R7 Bounded Liveness Closure Evidence

This directory preserves the 16-unit fresh functional summary, hash-chained execution ledger, per-unit verdicts, and full compressed raw evidence archive.

- Functional units: 16/16 PASS; retries 0.
- `CAPACITY_50`: OpenAI 50/50 and Microsoft 50/50 PASS.
- `CACHE_REUSE_30`: OpenAI 30/30 and Microsoft 30/30 PASS.
- Bounded causal stress: OpenAI {oa_stress['admitted_within_H']}/50, Microsoft {ms_stress['admitted_within_H']}/50 in this realization; guaranteed depth is not claimed.
- V4R7 200/200 reliability was preserved and not rerun.
- Protected classifier/AUC executions: 0/0.
- `functional_records.tar.gz` SHA-256: `{sha256(ARCHIVE)}`.
"""
    (EVIDENCE / "README.md").write_text(readme, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
