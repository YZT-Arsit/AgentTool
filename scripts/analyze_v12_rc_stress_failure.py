from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "results_v12_rc_routing_stress"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = RESULT_ROOT / "postmortem.json"
    if output.exists():
        raise FileExistsError("V12-RC stress postmortem is append-only")
    manifest_path = RESULT_ROOT / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dirs = sorted(
        (path for path in (RESULT_ROOT / "raw").iterdir() if path.is_dir()),
        key=lambda path: int(path.name.split("-", 1)[0]),
    )
    attempts = []
    for path in raw_dirs:
        index = int(path.name.split("-", 1)[0])
        identity = manifest["workflows"][index]
        result_path = path / "go_online_result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        statuses = [int(item["status"]) for item in result["results"]]
        actual_ids = [str(item["operation_id"]) for item in result["results"]]
        attempts.append(
            {
                "index": index,
                "workflow_id": identity["workflow_id"],
                "family": identity["family"],
                "framework": identity["framework"],
                "depth": identity["depth"],
                "session_status": result["session_status"],
                "rounds": len(result["public_relay_events"]),
                "schedule_misses": int(result["schedule_misses"]),
                "profile_overflow": int(result["profile_overflow_events"]),
                "silent_committed_result_loss": int(result["silent_committed_result_losses"]),
                "dummy_heavy_ops": int(result["dummy_provider_operations"]),
                "operation_ids_exact": actual_ids == identity["operation_ids"],
                "result_statuses": statuses,
                "all_results_success": statuses == [2] * int(identity["depth"]),
                "go_result_sha256": sha256(result_path),
            }
        )
    failing = [row for row in attempts if not row["all_results_success"]]
    if len(attempts) != 108 or len(failing) != 1 or failing[0]["index"] != 107:
        raise AssertionError("retained V12-RC partial campaign shape differs from observed failure")
    fail_dir = raw_dirs[-1]
    fail_result = json.loads((fail_dir / "go_online_result.json").read_text(encoding="utf-8"))
    first = fail_result["results"][0]
    value = {
        "schema": "AgentTool.V12RC.RoutingStressFailurePostmortem/1",
        "identity_manifest_sha256": sha256(manifest_path),
        "execution_started_sha256": sha256(RESULT_ROOT / "execution_started.json"),
        "planned_workflows": int(manifest["workflow_count"]),
        "canonical_workflows_started": len(attempts),
        "workflow_comparisons_completed_before_failure": 107,
        "openai_duplicate_name_stress": {
            "passed": 100,
            "planned": 100,
        },
        "microsoft_duplicate_name_stress": {
            "passed": 0,
            "planned": 100,
            "status": "NOT_RUN_EARLIER_DECISIVE_FAILURE",
        },
        "long_repeated_target": {
            "passed_before_failure": 7,
            "failed": 1,
            "not_run": 72,
            "planned": 80,
        },
        "failure": {
            "workflow_index": 107,
            "workflow_id": failing[0]["workflow_id"],
            "framework": failing[0]["framework"],
            "depth": failing[0]["depth"],
            "operation_id": first["operation_id"],
            "canonical_private_response_status": int(first["status"]),
            "canonical_status_name": "ERROR",
            "canonical_payload": first.get("payload"),
            "declared_scenario": "SUCCESS",
            "native_expected_status": "READ_ONLY:SUCCESS",
            "failure_class": "CANONICAL_PROVIDER_RESULT_ERROR_FIRST_OPERATION",
            "observed_assertion": "native/canonical repeated-name semantic mismatch",
            "session_status": fail_result["session_status"],
            "admitted": int(fail_result["admitted"]),
            "provider_invocations": int(fail_result["provider_invocations"]),
            "results": len(fail_result["results"]),
            "accepted_operation_ids": fail_result["accepted_operation_ids"],
            "result_operation_ids": [item["operation_id"] for item in fail_result["results"]],
            "schedule_misses": int(fail_result["schedule_misses"]),
            "profile_overflow": int(fail_result["profile_overflow_events"]),
            "silent_committed_result_loss": int(fail_result["silent_committed_result_losses"]),
            "dummy_heavy_ops": int(fail_result["dummy_provider_operations"]),
            "pending_operation_ids": fail_result["pending_operation_ids"],
            "private_alias_in_go_result": "acv_private_route_" in json.dumps(fail_result),
            "go_result_sha256": sha256(fail_dir / "go_online_result.json"),
            "private_trajectory_sha256": sha256(fail_dir / "private_trajectory.json"),
            "trusted_control_events_sha256": sha256(fail_dir / "trusted_control_events.jsonl"),
            "delivery_ledger_sha256": sha256(fail_dir / "trusted_delivery_ledger.json"),
            "gateway_effect_recovery_sha256": sha256(fail_dir / "gateway_state/effect_recovery.json"),
            "gateway_ready_results_sha256": sha256(fail_dir / "gateway_state/ready_results.json"),
        },
        "diagnostic_limit": "the frozen Go engine records only generic ERROR for provider HTTP transport, non-2xx, decode, or provider-status failure and discards the underlying error detail; the retained evidence cannot distinguish those subcauses without a new run",
        "retry_performed": False,
        "campaign_resumed": False,
        "selected_v12_cases_executed": 0,
        "v12_system_gate": "FAIL",
    }
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"attempted": len(attempts), "failed_index": 107, "status": "FAIL"}, sort_keys=True))


if __name__ == "__main__":
    main()
