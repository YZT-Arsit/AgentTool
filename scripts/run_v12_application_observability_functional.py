from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_pir_capacity_development import build_cases
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import delta_functional_candidate_profiles
from v12_timing.projection import (
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantile(values: Iterable[int], fraction: float) -> int:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        return 0
    return ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))]


def distribution(values: Iterable[int]) -> dict[str, int]:
    rows = list(values)
    return {"count": len(rows), "p50": quantile(rows, .50), "p95": quantile(rows, .95),
            "p99": quantile(rows, .99), "max": max(rows, default=0)}


def _trajectory_ids(value: dict[str, Any]) -> list[str]:
    return [str(row["operation_id"]) for row in value["projection"]["trajectory"]]


def run_one(output: Path, item: dict[str, Any], profile: Any) -> dict[str, Any]:
    identity = str(item["identity"])
    workflow, cases = build_cases(str(item["kind"]), str(item["framework"]), identity)
    prewarm_framework(str(item["framework"]))
    native = run_online_framework_workflow(str(item["framework"]), workflow, cases, native_implementation)
    started_ns = time.monotonic_ns()
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        canonical = run_online_framework_workflow(str(item["framework"]), workflow, cases, session.implementation())
    ended_ns = time.monotonic_ns()
    if session.trace is None:
        raise RuntimeError("canonical session produced no public trace")
    trace = session.trace
    pir_root = output / "pir"
    summary = json.loads((pir_root / "online_query_summary.json").read_text(encoding="utf-8"))
    registry_rows = load_registry_server_trace(pir_root / "server_visible_trace.jsonl")
    relay_projection = relay_timing_projection(
        {"public_relay_events": trace.get("public_relay_events", [])},
        expected_rounds=profile.total_rounds,
        require_complete_application_timing=True,
    )
    registry_projection = registry_timing_projection(
        registry_rows, profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
        require_complete_application_timing=True,
    )
    expected_ids = [case.operation_id for case in cases]
    external_ids = [case.operation_id for case in cases if case.placement != "TRUSTED_MODULE_LOCAL"]
    unique_agents = {case.agent_id for case in cases}
    expected_cache_hits = len(cases) - len(unique_agents)
    lifecycle = session.lifecycle
    recovered = [str(value["operation_id"]) for value in lifecycle if value["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"]
    delivered = [str(value["operation_id"]) for value in lifecycle if value["stage"] == "FRAMEWORK_RESULT_DELIVERED"]
    cover = json.loads((pir_root / "private_pir_cover_schedule.json").read_text(encoding="utf-8"))
    launches = trace.get("slot_launches", [])
    relay_events = trace.get("public_relay_events", [])
    common_checks = {
        "complete_relay_response_send_ns": len(relay_events) == profile.total_rounds and all(int(row.get("response_send_ns", 0)) > 0 for row in relay_events),
        "complete_registry_response_send_ns": len(registry_rows) == profile.pir_resolution_opportunities and all(int(row.get("response_send_ns", 0)) > 0 for row in registry_rows),
        "relay_complete_timing_projection": relay_projection["view"] == "TIMING_ONLY_VIEW",
        "registry_complete_timing_projection": registry_projection["view"] == "TIMING_ONLY_VIEW",
        "fixed_request_size": all(int(row["request_length"]) == 1079 for row in relay_events),
        "fixed_response_size": all(int(row["response_length"]) == 800 for row in relay_events),
        "no_infrastructure_liveness_failure": trace.get("infrastructure_liveness_failure") is False,
    }
    functional_checks = {
        "exact_native_operations": _trajectory_ids(native) == expected_ids,
        "exact_canonical_operations": _trajectory_ids(canonical) == expected_ids,
        "level_a_semantic_projection": native["projection"] == canonical["projection"],
        "exact_operation_ids_recovered": recovered == expected_ids,
        "exact_causal_order": delivered == expected_ids,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "exact_R_cells": int(trace.get("emitted_cells", -1)) == profile.total_rounds and len(relay_events) == profile.total_rounds,
        "fixed_slot_order": [int(row["round"]) for row in relay_events] == list(range(1, profile.total_rounds + 1)),
        "exact_external_accepted_ids": sorted(trace.get("accepted_operation_ids", [])) == sorted(external_ids),
        "exact_external_result_ids": sorted(row["operation_id"] for row in trace.get("results", [])) == sorted(external_ids),
        "expected_real_PIR_resolutions": int(summary["real_query_count"]) == len(unique_agents),
        "expected_trusted_cache_hits": int(summary["descriptor_cache_hits"]) == expected_cache_hits,
        "exact_Q_queries": int(summary["query_count"]) == 100 == profile.pir_resolution_opportunities,
        "real_plus_dummy_Q": int(summary["real_query_count"]) + int(summary["dummy_query_count"]) == 100,
        "no_out_of_schedule_PIR": len(cover) == 100 and all(int(row["ordinal"]) == index for index, row in enumerate(cover)),
        "zero_resolved_not_admitted": trace.get("resolved_not_admitted_ids", []) == [],
        "zero_profile_overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "zero_silent_committed_result_loss": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "zero_dummy_heavy_provider_operations": int(trace.get("dummy_provider_operations", -1)) == 0,
        "causal_proof": session.causal_proof()["passed"] is True,
    }
    slips = [int(row.get("launch_slip_ns", 0)) for row in launches]
    registry_gaps = [int(value) for value in registry_projection["inter_query_gap_ns"]]
    registry_response = [int(value) for value in registry_projection["query_response_ns"]]
    jitter = {
        "nominal_late_cells": int(trace.get("nominal_late_cells", 0)),
        "launch_slip_ns": distribution(slips),
        "session_wall_clock_span_ns": ended_ns - started_ns,
        "relay_application_span_ns": int(relay_projection["total_session_span_ns"]),
        "registry_inter_query_gap_ns": distribution(registry_gaps),
        "registry_request_response_ns": distribution(registry_response),
        "relay_response_send_complete": sum(int(row.get("response_send_ns", 0)) > 0 for row in relay_events),
        "registry_response_send_complete": sum(int(row.get("response_send_ns", 0)) > 0 for row in registry_rows),
    }
    record = {
        "schema": "AgentTool.V12ApplicationObservabilityFunctionalUnit/1",
        "identity": identity, "period_ms": profile.round_period_ms,
        "profile_id": profile.profile_id, "framework": item["framework"], "kind": item["kind"],
        "operation_count": len(cases), "expected_real_resolutions": len(unique_agents),
        "expected_cache_hits": expected_cache_hits,
        "common_checks": common_checks, "functional_checks": functional_checks,
        "common_integrity_pass": all(common_checks.values()),
        "functional_pass": all(functional_checks.values()),
        "jitter": jitter,
        "pir_summary_sha256": sha(pir_root / "online_query_summary.json"),
        "registry_trace_sha256": sha(pir_root / "server_visible_trace.jsonl"),
        "go_trace_sha256": sha(output / "go_online_result.json"),
        "classifier_training_runs": 0, "real_auc_calculations": 0,
    }
    (output / "functional_verdict.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite functional campaign: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("frozen_before_live_execution") is not True:
        raise ValueError("candidate manifest was not frozen before live execution")
    forbidden = tuple(manifest["forbidden_identity_prefixes"])
    identities = [str(row["identity"]) for row in manifest["workload_matrix"]]
    if len(set(identities)) != len(identities) or any(value.startswith(forbidden) for value in identities):
        raise ValueError("functional identities are reused or forbidden")
    profiles = {value.round_period_ms: value for value in delta_functional_candidate_profiles()}
    args.output.mkdir(parents=True)
    results: list[dict[str, Any]] = []
    abort: dict[str, Any] | None = None
    for period in manifest["Delta_candidates_ms"]:
        candidate_rows = [row for row in manifest["workload_matrix"] if int(row["period_ms"]) == int(period)]
        candidate: dict[str, Any] = {"period_ms": period, "profile_id": profiles[int(period)].profile_id,
                                     "status": "IN_PROGRESS", "workloads": []}
        for index, item in enumerate(candidate_rows):
            unit_root = args.output / f"P{period}" / f"{index:02d}_{item['identity']}"
            try:
                record = run_one(unit_root, item, profiles[int(period)])
            except BaseException as error:
                abort = {"status": "COMMON_PHASE_ABORT", "period_ms": period, "identity": item["identity"],
                         "exception_class": type(error).__name__, "exception_string": str(error),
                         "traceback": traceback.format_exc()}
                candidate["status"] = "NOT_RUN_DUE_COMMON_PHASE_ABORT"
                break
            candidate["workloads"].append({"identity": item["identity"], "functional_pass": record["functional_pass"],
                                           "common_integrity_pass": record["common_integrity_pass"],
                                           "verdict_sha256": sha(unit_root / "functional_verdict.json")})
            if not record["common_integrity_pass"]:
                abort = {"status": "COMMON_PHASE_ABORT", "period_ms": period, "identity": item["identity"],
                         "failed_checks": [key for key, value in record["common_checks"].items() if not value]}
                candidate["status"] = "NOT_RUN_DUE_COMMON_PHASE_ABORT"
                break
            if not record["functional_pass"]:
                candidate["status"] = "FUNCTIONAL_FAIL"
                candidate["first_failure_identity"] = item["identity"]
                break
        else:
            candidate["status"] = "FUNCTIONALLY_ELIGIBLE"
        results.append(candidate)
        (args.output / f"P{period}" / "candidate_verdict.json").write_text(
            json.dumps(candidate, indent=2) + "\n", encoding="utf-8", newline="\n")
        if abort is not None:
            break
    if abort is not None:
        completed_periods = {int(row["period_ms"]) for row in results}
        for period in manifest["Delta_candidates_ms"]:
            if int(period) not in completed_periods:
                results.append({"period_ms": period, "status": "NOT_RUN_DUE_COMMON_PHASE_ABORT", "workloads": []})
        (args.output / "common_phase_abort.json").write_text(json.dumps(abort, indent=2) + "\n", encoding="utf-8")
    completion = {
        "schema": "AgentTool.V12ApplicationObservabilityFunctionalCompletion/1",
        "manifest_sha256": sha(args.manifest), "candidate_results": results,
        "common_phase_abort": abort,
        "classifier_training_runs_on_real_traces": 0, "real_timing_auc_calculations": 0,
        "timing_confirmatory_sessions": 0, "selected_timing_delta_ms": "NONE",
        "selected_final_v12_cases_executed": 0,
    }
    (args.output / "campaign_completion.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 2 if abort is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
