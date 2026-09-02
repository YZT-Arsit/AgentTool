from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_pir_capacity_development import build_cases as build_capacity_cases
from v11_full_scope.fixtures import tool_case, with_readiness
from v11_full_scope.frameworks import native_implementation, run_framework_case
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import duplex_timing_candidate_profiles
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operation_id(identity: str, index: int) -> str:
    return "op" + hashlib.sha256(f"{identity}|{index}".encode()).hexdigest()[:28]


def framework_code(framework: str) -> str:
    return "OA" if framework == "OpenAI Agents SDK" else "MS"


def identity(delta_ms: int, framework: str, workload: str, suffix: str) -> str:
    return f"DEV-DTVR-V4R3-P{delta_ms}-{framework_code(framework)}-{workload}-{suffix}"


def build_workload(workload: str, framework: str, unit_identity: str):
    capacity_names = {
        "AGENT_AS_TOOL_TRANSITION": "AGENT_AS_TOOL_TRANSITION",
        "CAUSAL_DEPTH_50": "SAME_AGENT_CAUSAL_DEPTH_50",
        "DESCRIPTOR_TRANSITIONS_K6": "MAX_K_DISTINCT_AGENT_RESOLUTIONS",
        "CACHE_REUSE_30": "SAME_AGENT_CACHE_HIT_30",
    }
    if workload in capacity_names:
        return build_capacity_cases(
            capacity_names[workload], framework, unit_identity
        )
    count = 1 if workload == "ORDINARY_TOOL" else 10
    cases = []
    for index in range(count):
        value = replace(
            tool_case(f"{unit_identity}-A{index:02d}", framework),
            operation_id=operation_id(unit_identity, index),
            capability="tool.read",
            logical_action_name=(
                "ordinary_tool"
                if workload == "ORDINARY_TOOL"
                else "repeated_private_target"
                if workload == "REPEATED_TARGET_10"
                else f"provider_readiness_step_{index}"
            ),
        ).validate()
        if workload == "PROVIDER_EARLY_10":
            value = with_readiness(value, "EARLY_READY").validate()
        elif workload == "PROVIDER_LATE_10":
            value = with_readiness(value, "LATE_READY_WITHIN_BOUND").validate()
        elif workload not in {"ORDINARY_TOOL", "REPEATED_TARGET_10"}:
            raise ValueError(f"unknown duplex functional workload: {workload}")
        cases.append(value)
    return "DYNAMIC_SEQUENCE", cases


def trajectory_ids(value: dict[str, Any]) -> list[str]:
    return [str(row["operation_id"]) for row in value["projection"]["trajectory"]]


def run_one(
    output: Path,
    profile: Any,
    framework: str,
    workload: str,
    unit_identity: str,
) -> dict[str, Any]:
    workflow, cases = build_workload(workload, framework, unit_identity)
    prewarm_framework(framework)
    native_records = [run_framework_case(case, native_implementation) for case in cases]
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        canonical = run_online_framework_workflow(
            framework, workflow, cases, session.implementation()
        )
    if session.trace is None:
        raise RuntimeError("duplex functional session produced no runtime trace")
    trace = session.trace
    relay_events = trace.get("public_relay_events", [])
    registry_root = output / "pir"
    registry_rows = load_registry_server_trace(
        registry_root / "server_visible_trace.jsonl"
    )
    registry_summary = json.loads(
        (registry_root / "online_query_summary.json").read_text(encoding="utf-8")
    )
    relay_projection = relay_timing_projection(
        {"public_relay_events": relay_events},
        expected_rounds=profile.total_rounds,
        expected_request_bytes=1079,
        expected_response_bytes=800,
        require_complete_application_timing=True,
        require_duplex_application_timing=True,
    )
    registry_projection = registry_timing_projection(
        registry_rows,
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
        require_complete_application_timing=True,
    )
    expected_ids = [case.operation_id for case in cases]
    external_ids = [
        case.operation_id
        for case in cases
        if case.placement != "TRUSTED_MODULE_LOCAL"
    ]
    unique_agents = {case.agent_id for case in cases}
    lifecycle = session.lifecycle
    recovered = [
        str(row["operation_id"])
        for row in lifecycle
        if row["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"
    ]
    delivered = [
        str(row["operation_id"])
        for row in lifecycle
        if row["stage"] == "FRAMEWORK_RESULT_DELIVERED"
    ]
    releases = trace.get("gateway_response_releases", [])
    common_checks = {
        "duplex_profile_exact": trace.get("profile_id") == profile.profile_id,
        "complete_relay_transcript": len(relay_events) == profile.total_rounds,
        "complete_registry_transcript": len(registry_rows) == 100,
        "relay_duplex_projection": relay_projection["view"]
        == DUPLEX_TIMING_ONLY_VIEW,
        "registry_complete_projection": registry_projection["view"]
        == "TIMING_ONLY_VIEW",
        "four_relay_application_boundaries": all(
            all(
                int(row.get(field, 0)) > 0
                for field in (
                    "client_to_relay_receive_ns",
                    "relay_to_gateway_send_ns",
                    "gateway_to_relay_receive_ns",
                    "relay_to_client_send_ns",
                )
            )
            for row in relay_events
        ),
        "gateway_release_clock_complete": len(releases) == profile.total_rounds,
        "gateway_release_deadlines_met": all(
            not bool(row.get("deadline_miss")) for row in releases
        ),
        "fixed_relay_request_bytes": all(
            int(row["request_length"]) == 1079 for row in relay_events
        ),
        "fixed_relay_response_bytes": all(
            int(row["response_length"]) == 800 for row in relay_events
        ),
        "fixed_registry_query_shape": len(
            {
                (
                    int(row["query_bytes"]),
                    int(row["query_rows"]),
                    int(row["query_cols"]),
                )
                for row in registry_rows
            }
        )
        == 1,
        "fixed_registry_answer_bytes": len(
            {int(row["answer_bytes"]) for row in registry_rows}
        )
        == 1,
        "no_infrastructure_liveness_failure": trace.get(
            "infrastructure_liveness_failure"
        )
        is False,
    }
    functional_checks = {
        "exact_native_operations": len(native_records) == len(expected_ids),
        "exact_canonical_operations": trajectory_ids(canonical) == expected_ids,
        "level_a_semantics": all(
            (
                row.selected_logical_action,
                row.arguments,
                row.provider_visible_logical_request,
                row.effect_count,
                row.operation_outcome_semantics,
                row.result,
            )
            == (
                canonical_row["logical_action"],
                canonical_row["arguments"],
                canonical_row["provider_visible_logical_request"],
                canonical_row["effect_count"],
                canonical_row["outcome"],
                canonical_row["result"],
            )
            for row, canonical_row in zip(
                native_records, canonical["projection"]["trajectory"], strict=True
            )
        ),
        "exact_operation_ids_recovered": recovered == expected_ids,
        "exact_causal_delivery_order": delivered == expected_ids,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete")
        is True,
        "exact_external_accepted_ids": sorted(
            trace.get("accepted_operation_ids", [])
        )
        == sorted(external_ids),
        "exact_external_results": sorted(
            row["operation_id"] for row in trace.get("results", [])
        )
        == sorted(external_ids),
        "expected_real_registry_resolutions": int(
            registry_summary["real_query_count"]
        )
        == len(unique_agents),
        "expected_descriptor_cache_hits": int(
            registry_summary["descriptor_cache_hits"]
        )
        == len(cases) - len(unique_agents),
        "exact_Q": int(registry_summary["query_count"])
        == int(registry_summary["real_query_count"])
        + int(registry_summary["dummy_query_count"])
        == 100,
        "query_sender_open_loop": registry_summary[
            "query_sender_waits_for_prior_completion"
        ]
        is False,
        "zero_resolved_not_admitted": trace.get("resolved_not_admitted_ids", [])
        == [],
        "zero_silent_loss": int(trace.get("silent_committed_result_losses", -1))
        == 0,
        "zero_profile_overflow": int(trace.get("profile_overflow_events", -1))
        == 0,
        "zero_dummy_provider_work": int(trace.get("dummy_provider_operations", -1))
        == 0,
        "causal_proof": session.causal_proof()["passed"] is True,
    }
    result = {
        "schema": "AgentTool.V12DuplexFunctionalUnit/1",
        "identity": unit_identity,
        "profile_id": profile.profile_id,
        "delta_ms": profile.round_period_ms,
        "framework": framework,
        "workload": workload,
        "operation_count": len(cases),
        "common_checks": common_checks,
        "functional_checks": functional_checks,
        "common_integrity_pass": all(common_checks.values()),
        "functional_pass": all(functional_checks.values()),
        "registry_query_bytes": sorted(
            {int(row["query_bytes"]) for row in registry_rows}
        ),
        "registry_answer_bytes": sorted(
            {int(row["answer_bytes"]) for row in registry_rows}
        ),
        "classifier_training_runs": 0,
        "auc_calculations": 0,
        "retries": 0,
    }
    (output / "duplex_functional_verdict.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite duplex evidence: {args.output}")
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    if freeze.get("frozen_before_functional_execution") is not True:
        raise ValueError("duplex functional definitions were not frozen")
    profiles = {p.round_period_ms: p for p in duplex_timing_candidate_profiles()}
    suffix = str(freeze["identity_suffix"])
    for frozen_profile in freeze["profiles"]:
        profile = profiles[int(frozen_profile["delta_ms"])]
        if (
            frozen_profile["profile_id"] != profile.profile_id
            or int(frozen_profile["R"]) != profile.total_rounds
        ):
            raise ValueError("duplex functional profile freeze disagrees with code")
    planned = [
        (profiles[int(profile["delta_ms"])], framework, workload)
        for profile in freeze["profiles"]
        for framework in freeze["frameworks"]
        for workload in freeze["workloads"]
    ]
    identities = [identity(p.round_period_ms, f, w, suffix) for p, f, w in planned]
    if len(planned) != freeze["planned_identities"] or len(set(identities)) != len(
        identities
    ):
        raise ValueError("duplex functional identity freeze is malformed")
    args.output.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    for index, (profile, framework, workload) in enumerate(planned):
        unit_identity = identity(profile.round_period_ms, framework, workload, suffix)
        unit_root = args.output / f"{index:02d}_{unit_identity}"
        started_ns = time.time_ns()
        try:
            record = run_one(
                unit_root, profile, framework, workload, unit_identity
            )
        except Exception as error:  # noqa: BLE001 - preserve every frozen unit failure
            record = {
                "identity": unit_identity,
                "profile_id": profile.profile_id,
                "delta_ms": profile.round_period_ms,
                "framework": framework,
                "workload": workload,
                "common_integrity_pass": False,
                "functional_pass": False,
                "exception_class": type(error).__name__,
                "exception_string": str(error),
                "traceback": traceback.format_exc(),
                "started_ns": started_ns,
                "ended_ns": time.time_ns(),
                "classifier_training_runs": 0,
                "auc_calculations": 0,
                "retries": 0,
            }
            (args.output / f"failure_{index:02d}.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        records.append(record)
        if not bool(record["common_integrity_pass"]):
            break
    summary = {
        "schema": "AgentTool.V12DuplexFunctionalCompletion/1",
        "freeze_sha256": sha(args.freeze),
        "planned_identities": len(planned),
        "executed_identities": len(records),
        "retries": 0,
        "passed": sum(
            bool(row["common_integrity_pass"] and row["functional_pass"])
            for row in records
        ),
        "failed": sum(
            not bool(row["common_integrity_pass"] and row["functional_pass"])
            for row in records
        ),
        "by_framework": {
            framework: {
                "passed": sum(
                    row["framework"] == framework
                    and bool(row["common_integrity_pass"] and row["functional_pass"])
                    for row in records
                ),
                "total": sum(row["framework"] == framework for row in records),
            }
            for framework in freeze["frameworks"]
        },
        "by_delta": {
            str(delta): {
                "passed": sum(
                    int(row["delta_ms"]) == delta
                    and bool(row["common_integrity_pass"] and row["functional_pass"])
                    for row in records
                ),
                "total": sum(int(row["delta_ms"]) == delta for row in records),
            }
            for delta in profiles
        },
        "records": records,
        "protected_classifier_training_runs": 0,
        "protected_auc_calculations": 0,
        "new_protected_timing_sessions": 0,
        "common_integrity_abort": any(
            not bool(row["common_integrity_pass"]) for row in records
        ),
    }
    (args.output / "completion.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
