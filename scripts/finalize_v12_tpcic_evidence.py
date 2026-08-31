from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_pir_capacity_development import build_cases


def sha(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def write_json(name: str, value: dict[str, object]) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    failed_identity = "DEV-TPCIC-MS-SAME-AGENT-DEPTH50-001"
    _, cases = build_cases("SAME_AGENT_CAUSAL_DEPTH_50", "Microsoft Agent Framework", failed_identity)
    expected = [case.operation_id for case in cases]
    executed = expected[:40]
    exception = (
        "Microsoft online workflow operation-ID execution mismatch: "
        f"expected={expected!r} executed={executed!r}"
    )
    failure = {
        "schema": "AgentTool.V12TPCICLiveCapacityFailure/1",
        "campaign_root": "/root/autodl-tmp/results_v12_tpcic_live_capacity",
        "status": "FAIL_STOPPED_AT_FIRST_LIVE_CAPACITY_FAILURE",
        "completed_ledger_records": 1,
        "completed_passed_workloads": 1,
        "failed_workload_index": 1,
        "failed_identity": failed_identity,
        "failed_stage": "NATIVE_FRAMEWORK_BEFORE_CANONICAL_SESSION_CREATION",
        "framework": "Microsoft Agent Framework",
        "expected_operation_count": 50,
        "executed_operation_count": 40,
        "first_missing_operation_index": 40,
        "first_missing_operation_id": expected[40],
        "expected_operation_ids": expected,
        "executed_operation_ids": executed,
        "exception_class": "AssertionError",
        "exception_string": exception,
        "mechanical_root_cause": {
            "class": "MICROSOFT_NATIVE_FRAMEWORK_DEFAULT_MAX_ITERATIONS",
            "value": 40,
            "source": "external_stage9/agent-framework/python/packages/core/agent_framework/_tools.py",
            "source_sha256": sha("external_stage9/agent-framework/python/packages/core/agent_framework/_tools.py"),
            "evidence": "DEFAULT_MAX_ITERATIONS is 40 and the current adapter did not override it for the 50-step native workflow",
        },
        "canonical_session_created_for_failed_workload": False,
        "pir_queries_for_failed_workload": 0,
        "retry_count": 0,
        "replacement_count": 0,
        "remaining_workloads_executed": 0,
        "campaign_driver_exit_code": 1,
        "raw_remote_root_preserved": True,
        "bindings": {
            "execution_ledger.jsonl": sha("V12_TPCIC_LIVE_CAPACITY_EXECUTION_LEDGER.jsonl"),
            "first_pass_verdict.json": sha("V12_TPCIC_LIVE_CAPACITY_FIRST_VERDICT.json"),
            "first_pass_pir_summary.json": sha("V12_TPCIC_LIVE_CAPACITY_FIRST_PIR_SUMMARY.json"),
        },
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    closure = {
        "schema": "AgentTool.V12TimingPIRCapacityIntegrityClosure/1",
        "phase": "V12-TIMING-PIR-CAPACITY-INTEGRITY-CLOSURE",
        "base_commit": "16e0c83adb5f7548b3b0815fed06ddc99cf4bbf0",
        "PRIOR_TIMING_DEVELOPMENT_ABORT": "PRESERVED",
        "PRIOR_FAILED_IDENTITY": "DEV-TD-CAPACITY50-P10-PIR60 NEVER_RETRIED",
        "DEPLOYMENT_INTEGRITY_ROOT_CAUSE": "STALE_REMOTE_TRANSITIVE_RUNTIME",
        "TRANSITIVE_RUNTIME_MANIFEST": "PASS",
        "REMOTE_RUNTIME_HASH_MATCH": "696/696",
        "PYTHON_MODULE_FILE_PROBES": "10/10",
        "BINARY_HASH_MATCH": "2/2",
        "PIR_INITIAL_LEAD_PREFLIGHT": "PASS",
        "OLD_Q_EQUALS_M_RULE": "REJECTED",
        "PIR_RESOLUTION_SEMANTIC_UNIT": (
            "first activation/change/Agent-as-Tool target/epoch invalidation per authenticated (catalog_epoch, agent_id); "
            "same unchanged Agent descriptor is reused inside the trusted session"
        ),
        "MAX_REAL_AGENT_RESOLUTIONS_K": 6,
        "PIR_COVER_CONSTRUCTION": "FIXED_PUBLIC_EPOCH",
        "PIR_PERIOD_MS": 60,
        "PIR_PUBLIC_EPOCH_MS": 6000,
        "FIXED_PIR_QUERY_COUNT_Q": 100,
        "PIR_CAUSAL_CAPACITY_MODEL": "PASS",
        "JOINT_PIR_ACTION_CAPACITY_PROOF": "PASS",
        "POST_CHANGE_NON_TIMING_PYTHON_SERIAL": "51/51 PASS",
        "POST_CHANGE_NON_TIMING_PYTHON_DEFAULT": "51/51 PASS",
        "POST_CHANGE_NATIVE_ROUTING": "15/15 PASS",
        "POST_CHANGE_GO": "70/70 PASS",
        "POST_CHANGE_SECURITY_NEGATIVES": "22/22 PASS",
        "FRESH_LIVE_CAPACITY": "FAIL: 1/5 PASS THEN MICROSOFT NATIVE DEPTH50 STOP AT 40/50",
        "FRESH_LIVE_CAPACITY_FAILURE": "V12_TPCIC_LIVE_CAPACITY_FAILURE.json",
        "TIMING_ATTACK_SESSIONS": 0,
        "TIMING_CONFIRMATORY_SESSIONS": 0,
        "TIMING_PRIVACY": "INCONCLUSIVE",
        "TIMING_GO": "NO",
        "PACKET_LEVEL_TIMING": "OPEN",
        "HARDWARE_TEE": "NOT_TESTED",
        "V12_FINAL_CANDIDATE_UNIVERSE_EXISTS": False,
        "V12_FINAL_SEED_EXISTS": False,
        "SELECTED_FINAL_V12_CASES_EXECUTED": 0,
        "READY_TO_RESUME_TIMING_ATTACK_DEVELOPMENT": "NO",
        "READY_FOR_FINAL_V12_HOLDOUT": "NO",
        "evidence_sha256": {
            name: sha(name)
            for name in (
                "V12_TIMING_TRANSITIVE_RUNTIME_MANIFEST.json",
                "V12_TIMING_DEPLOYMENT_VERIFICATION_V2.json",
                "V12_PIR_INITIAL_LEAD_PREFLIGHT_V2.json",
                "V12_PIR_RESOLUTION_SEMANTICS.json",
                "V12_PIR_CAUSAL_CAPACITY_MODEL.json",
                "V12_JOINT_PIR_ACTION_CAPACITY_PROOF.json",
                "V12_TPCIC_POST_CHANGE_PYTHON_SERIAL.json",
                "V12_TPCIC_POST_CHANGE_PYTHON_DEFAULT.json",
                "V12_TPCIC_POST_CHANGE_GO.txt",
                "V12_TPCIC_POST_CHANGE_SECURITY_NEGATIVES.json",
                "V12_TPCIC_LIVE_CAPACITY_MANIFEST.json",
            )
        },
    }
    write_json("V12_TPCIC_LIVE_CAPACITY_FAILURE.json", failure)
    write_json("V12_TIMING_PIR_CAPACITY_INTEGRITY_CLOSURE.json", closure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
