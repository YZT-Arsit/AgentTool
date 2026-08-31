from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.fixtures import agent_case, tool_case
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import AgentServiceSubtype
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import TimingIndistinguishabilityProfile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operation_id(identity: str, index: int) -> str:
    return "op" + hashlib.sha256(f"{identity}|{index}".encode()).hexdigest()[:28]


def build_cases(kind: str, framework: str, identity: str):
    if kind == "SAME_AGENT_CAUSAL_DEPTH_50":
        return "DYNAMIC_SEQUENCE", [
            replace(
                tool_case(f"{identity}-A{index:02d}", framework),
                operation_id=operation_id(identity, index),
                logical_action_name="repeated_same_agent_tool",
            ).validate()
            for index in range(50)
        ]
    if kind == "MAX_K_DISTINCT_AGENT_RESOLUTIONS":
        values = [
            tool_case(f"{identity}-A00", framework),
            agent_case(f"{identity}-A01", framework, AgentServiceSubtype.DIRECT_AGENT_SERVICE, "READ_ONLY"),
            agent_case(f"{identity}-A02", framework, AgentServiceSubtype.DIRECT_AGENT_SERVICE, "IDEMPOTENT_EFFECT"),
            agent_case(f"{identity}-A03", framework, AgentServiceSubtype.DIRECT_AGENT_SERVICE, "NON_IDEMPOTENT_EFFECT"),
            agent_case(
                f"{identity}-A04",
                framework,
                AgentServiceSubtype.DIRECT_AGENT_SERVICE,
                "READ_ONLY",
                placement="TRUSTED_MODULE_LOCAL",
            ),
            replace(
                tool_case(f"{identity}-A05", framework),
                agent_id=21,
                agent_capability="agent.workflow.21",
            ).validate(),
        ]
        return "DYNAMIC_SEQUENCE", [
            replace(value, operation_id=operation_id(identity, index), logical_action_name=f"distinct_agent_step_{index}").validate()
            for index, value in enumerate(values)
        ]
    if kind == "AGENT_AS_TOOL_TRANSITION":
        values = [
            tool_case(f"{identity}-A00", framework),
            agent_case(f"{identity}-A01", framework, AgentServiceSubtype.AGENT_AS_TOOL),
        ]
        return "TOOL_TO_AGENT_AS_TOOL", [
            replace(value, operation_id=operation_id(identity, index), logical_action_name="capacity_transition").validate()
            for index, value in enumerate(values)
        ]
    raise ValueError(f"unknown capacity workload kind: {kind}")


def run_one(output: Path, item: dict[str, str], profile: TimingIndistinguishabilityProfile) -> dict[str, object]:
    identity = item["identity"]
    if identity == "DEV-TD-CAPACITY50-P10-PIR60":
        raise ValueError("the prior failed identity may never be retried")
    workflow, cases = build_cases(item["kind"], item["framework"], identity)
    prewarm_framework(item["framework"])
    native = run_online_framework_workflow(item["framework"], workflow, cases, native_implementation)
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        canonical = run_online_framework_workflow(item["framework"], workflow, cases, session.implementation())
    assert session.trace is not None
    trace = session.trace
    summary = json.loads((output / "pir" / "online_query_summary.json").read_text(encoding="utf-8"))
    expected_ids = [case.operation_id for case in cases]
    external_ids = [case.operation_id for case in cases if case.placement != "TRUSTED_MODULE_LOCAL"]
    lifecycle = session.lifecycle
    recovered = [value["operation_id"] for value in lifecycle if value["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"]
    delivered = [value["operation_id"] for value in lifecycle if value["stage"] == "FRAMEWORK_RESULT_DELIVERED"]
    unique_agents = {case.agent_id for case in cases}
    checks = {
        "semantic_projection_equal": native["projection"] == canonical["projection"],
        "causal_proof": session.causal_proof()["passed"],
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "exact_rounds": int(trace.get("emitted_cells", -1)) == profile.total_rounds,
        "exact_operation_ids_recovered": recovered == expected_ids,
        "exact_operation_ids_delivered": delivered == expected_ids,
        "exact_external_accepted_ids": sorted(trace.get("accepted_operation_ids", [])) == sorted(external_ids),
        "exact_external_result_ids": sorted(value["operation_id"] for value in trace.get("results", [])) == sorted(external_ids),
        "fixed_total_pir_queries": summary["query_count"] == profile.pir_resolution_opportunities,
        "exact_real_resolution_count": summary["real_query_count"] == len(unique_agents),
        "exact_dummy_query_count": summary["dummy_query_count"] == profile.pir_resolution_opportunities - len(unique_agents),
        "cache_accounting": summary["descriptor_cache_hits"] + summary["descriptor_cache_misses"] == len(cases),
        "no_dummy_heavy": int(trace.get("dummy_provider_operations", -1)) == 0,
        "no_silent_loss": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "no_profile_overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "no_infrastructure_liveness_failure": trace.get("infrastructure_liveness_failure") is False,
        "fixed_request_size": all(int(value["request_length"]) == 1079 for value in trace.get("public_relay_events", [])),
        "fixed_response_size": all(int(value["response_length"]) == 800 for value in trace.get("public_relay_events", [])),
    }
    record = {
        "schema": "AgentTool.V12TPCICLiveCapacityResult/1",
        "identity": identity,
        "kind": item["kind"],
        "framework": item["framework"],
        "operation_count": len(cases),
        "unique_agent_resolution_count": len(unique_agents),
        "checks": checks,
        "passed": all(checks.values()),
        "pir_summary_sha256": sha(output / "pir" / "online_query_summary.json"),
        "go_trace_sha256": sha(output / "go_online_result.json"),
        "timing_attack_session": False,
    }
    (output / "capacity_verdict.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite live capacity root: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    forbidden_identities = set(manifest.get("forbidden_identities", [manifest["prior_failed_identity"]]))
    forbidden_prefixes = tuple(manifest.get("forbidden_identity_prefixes", []))
    for item in manifest["workloads"]:
        identity = item["identity"]
        if identity in forbidden_identities or identity.startswith(forbidden_prefixes):
            raise ValueError(f"prior capacity identity was selected for retry: {identity}")
    args.output.mkdir(parents=True)
    profile = TimingIndistinguishabilityProfile(
        profile_id="V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        round_period_ms=10,
        pir_resolution_period_ms=60,
    ).validate()
    ledger = args.output / "execution_ledger.jsonl"
    previous = "0" * 64
    for index, item in enumerate(manifest["workloads"]):
        started = time.time_ns()
        try:
            record = run_one(args.output / f"{index:02d}_{item['identity']}", item, profile)
        except Exception as error:
            failure = {
                "schema": "AgentTool.V12LiveCapacityFailure/1",
                "index": index,
                "identity": item["identity"],
                "kind": item["kind"],
                "framework": item["framework"],
                "started_ns": started,
                "ended_ns": time.time_ns(),
                "status": "FAIL_STOPPED_NO_RETRY",
                "exception_class": type(error).__name__,
                "exception_string": str(error),
                "traceback": traceback.format_exc(),
                "retry_count": 0,
                "replacement_count": 0,
                "timing_attack_session": False,
            }
            failure_path = args.output / "campaign_failure.json"
            failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8", newline="\n")
            ledger_record = {
                "index": index,
                "identity": item["identity"],
                "started_ns": started,
                "ended_ns": failure["ended_ns"],
                "passed": False,
                "failure_sha256": sha(failure_path),
                "previous_record_sha256": previous,
            }
            encoded = json.dumps(ledger_record, sort_keys=True, separators=(",", ":"))
            with ledger.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded + "\n")
            return 2
        ledger_record = {
            "index": index,
            "identity": item["identity"],
            "started_ns": started,
            "ended_ns": time.time_ns(),
            "passed": record["passed"],
            "verdict_sha256": sha(args.output / f"{index:02d}_{item['identity']}" / "capacity_verdict.json"),
            "previous_record_sha256": previous,
        }
        encoded = json.dumps(ledger_record, sort_keys=True, separators=(",", ":"))
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
        previous = hashlib.sha256(encoded.encode()).hexdigest()
        if not record["passed"]:
            (args.output / "campaign_failure.json").write_text(
                json.dumps({"first_failure": record, "completed": index + 1}, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return 2
    results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.output.glob("*_DEV-*/capacity_verdict.json"))
    ]
    completion = {
        "schema": "AgentTool.V12TPCICLiveCapacityCompletion/1",
        "workloads": len(results),
        "passed": sum(bool(value["passed"]) for value in results),
        "status": "PASS" if len(results) == len(manifest["workloads"]) and all(value["passed"] for value in results) else "FAIL",
        "final_ledger_record_sha256": previous,
        "ledger_sha256": sha(ledger),
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    (args.output / "campaign_completion.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if completion["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
