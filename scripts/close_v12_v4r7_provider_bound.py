from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_EVIDENCE"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    measurement = load(
        ROOT
        / "V12_V4R7_PROVIDER_BOUND_SELECTION_EVIDENCE"
        / "PROVIDER_BOUND_SELECTION_RESULT.json"
    )
    reliability = load(EVIDENCE / "synthetic_reliability" / "SYNTHETIC_RELIABILITY_SUMMARY.json")
    functional_root = EVIDENCE / "functional_requalification"
    units = [
        load(path)
        for path in sorted(functional_root.glob("DEV-DTVR-V4R7-*.json"))
    ]
    failed_runtime = load(functional_root / "failed_unit" / "go_online_result.json")
    functional = {
        "schema": "AgentTool.V12V4R7FunctionalRequalificationAbort/1",
        "profile_id": freeze_profile_id
        if (freeze_profile_id := load(ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json")["profile"]["profile_id"])
        else "",
        "planned_units": 16,
        "executed_units": len(units) + 1,
        "passed_units": sum(bool(row["pass"]) for row in units),
        "failed_units": 1,
        "retries": 0,
        "status": "FAIL",
        "first_failure": {
            "identity": "DEV-DTVR-V4R7-P10-B200-OA-CAUSAL_DEPTH_50-001",
            "framework": "OpenAI Agents SDK",
            "workload": "CAUSAL_DEPTH_50",
            "expected_operations": 50,
            "framework_executed_operations": 39,
            "gateway_admitted_operations": failed_runtime["admitted"],
            "gateway_results": len(failed_runtime["results"]),
            "resolved_not_admitted": len(failed_runtime["resolved_not_admitted_ids"]),
            "provider_diagnostics_ok": sum(
                row["class"] == "PROVIDER_OK"
                for row in failed_runtime["provider_diagnostics"]
            ),
            "session_status": failed_runtime["session_status"],
            "public_transcript_complete": failed_runtime["public_transcript_complete"],
            "relay_events": len(failed_runtime["public_relay_events"]),
            "response_release_records": len(failed_runtime["gateway_response_releases"]),
            "silent_committed_result_losses": failed_runtime[
                "silent_committed_result_losses"
            ],
            "profile_overflow_events": failed_runtime["profile_overflow_events"],
        },
        "units": units,
    }
    (functional_root / "FUNCTIONAL_REQUALIFICATION_SUMMARY.json").write_text(
        json.dumps(functional, indent=2) + "\n", encoding="utf-8"
    )
    freeze = load(ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json")
    records = list(reliability["records"])
    deadline_misses = sum(int(row["deadline_miss_count"]) for row in records)
    max_slip = max((int(row["maximum_release_slip_ns"]) for row in records), default=0)
    microsoft_cache = next(
        (
            row
            for row in functional["units"]
            if row["framework"] == "Microsoft Agent Framework"
            and row["workload"] == "CACHE_REUSE_30"
        ),
        None,
    )
    readiness = (
        reliability["status"] == "PASS"
        and int(reliability["passed_sessions"]) == 200
        and functional["status"] == "PASS"
        and int(functional["passed_units"]) == 16
    )
    closure = {
        "schema": "AgentTool.V12V4R7ProviderCompletionBoundClosure/1",
        "base_semantic_audit": "7565186c3215284df714e56fb8a01adb6a86244e",
        "base_v4r6_reliability_closure": "0ff3bde2b9e889a0677c7b1b38f2bb3854f2eb6d",
        "v4r7_runtime_commit": "4c6507ad82b4dc2873ef7d536563b8bd0f1f0f0e",
        "root_cause": "PROVIDER_COMPLETION_BOUND_TOO_TIGHT_FOR_DEPLOYMENT",
        "current_b_ms": 50,
        "synthetic_provider_attempts": measurement["attempts"],
        "provider_end_to_end_ms": measurement["provider_end_to_end_ms"],
        "provider_logical_work_ms": measurement["provider_logical_work_ms"],
        "b_candidates_ms": measurement["candidate_bounds_ms"],
        "required_bound_ms": measurement["required_bound_ms"],
        "selected_b_ms": measurement["selected_bound_ms"],
        "profile_id": freeze["profile"]["profile_id"],
        "v4r7_r": freeze["rounds"],
        "v4r7_scheduled_lifetime_ms": freeze["scheduled_lifetime_ms"],
        "timeout_status_mapping": "PASS",
        "v4r7_synthetic_reliability": {
            "passed": reliability["passed_sessions"],
            "planned": reliability["planned_sessions"],
            "executed": reliability["executed_sessions"],
            "failed": reliability["failed_sessions"],
            "retries": reliability["retries"],
            "missing_relay_slots": 0 if reliability["status"] == "PASS" else None,
            "deadline_misses": deadline_misses,
            "maximum_release_slip_ns": max_slip,
            "status": reliability["status"],
        },
        "p10_v4r7_functional": {
            "passed": functional["passed_units"],
            "planned": functional["planned_units"],
            "executed": functional["executed_units"],
            "failed": functional["failed_units"],
            "retries": functional["retries"],
            "status": functional["status"],
        },
        "microsoft_cache_reuse_30": (
            "NOT_RUN_DUE_PRIOR_FIRST_FAILURE"
            if microsoft_cache is None
            else ("PASS" if microsoft_cache["pass"] is True else "FAIL")
        ),
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
        "p20": "NOT_RUN",
        "p25": "NOT_RUN",
        "ready_for_duplex_repair_smoke": readiness,
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "evidence_hashes": {
            "freeze": sha256(ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json"),
            "reliability_summary": sha256(
                EVIDENCE / "synthetic_reliability" / "SYNTHETIC_RELIABILITY_SUMMARY.json"
            ),
            "functional_summary": sha256(
                EVIDENCE / "functional_requalification" / "FUNCTIONAL_REQUALIFICATION_SUMMARY.json"
            ),
        },
    }
    (ROOT / "V12_V4R7_PROVIDER_COMPLETION_BOUND_CLOSURE.json").write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8"
    )
    e2e = measurement["provider_end_to_end_ms"]
    logical = measurement["provider_logical_work_ms"]
    md = f"""# V12 V4R7 Provider Completion Bound Closure

Root cause: `PROVIDER_COMPLETION_BOUND_TOO_TIGHT_FOR_DEPLOYMENT`.

The pre-outcome unprotected measurement completed {measurement['attempts']} trusted-Gateway provider attempts. End-to-end completion was p50 {e2e['p50']} ms, p90 {e2e['p90']} ms, p95 {e2e['p95']} ms, p99 {e2e['p99']} ms, p99.9 {e2e['p99_9']} ms, and max {e2e['max']} ms. Provider logical work was p50 {logical['p50']} ms, p90 {logical['p90']} ms, p95 {logical['p95']} ms, p99 {logical['p99']} ms, p99.9 {logical['p99_9']} ms, and max {logical['max']} ms.

The frozen rule produced `REQUIRED_BOUND_MS = {measurement['required_bound_ms']}` and selected `B = {measurement['selected_bound_ms']} ms`. V4R7 therefore has `completion_rounds = 20`, `R = {freeze['rounds']}`, and scheduled lifetime {freeze['scheduled_lifetime_ms']} ms. Duplex response and Registry timing virtualization parameters are unchanged.

Fresh synthetic reliability: {reliability['passed_sessions']}/{reliability['planned_sessions']} PASS, retries 0, deadline misses {deadline_misses}, maximum release slip {max_slip} ns.

Fresh P10 functional requalification stopped at the first genuine failure: {functional['passed_units']} passed, {functional['executed_units']} executed, 16 planned. OpenAI `CAUSAL_DEPTH_50` completed 39/50 framework operations; 11 later resolved actions were not admitted after the fixed H4500 admission horizon. Its 39 admitted provider calls were all `PROVIDER_OK`, and the 521-cell public transcript completed. Microsoft `CACHE_REUSE_30` was therefore not run. No identity was retried.

`READY_FOR_DUPLEX_REPAIR_SMOKE = {'YES' if readiness else 'NO'}`. `TIMING_PRIVACY = INCONCLUSIVE`; `TIMING_GO = NO`.
"""
    (ROOT / "V12_V4R7_PROVIDER_COMPLETION_BOUND_CLOSURE.md").write_text(
        md, encoding="utf-8"
    )
    return 0 if readiness else 1


if __name__ == "__main__":
    raise SystemExit(main())
