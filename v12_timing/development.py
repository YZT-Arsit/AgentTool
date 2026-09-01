from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v11_full_scope.canonical import _canonical_ids
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession

from .isolated_tasks import PrimaryTimingWorkload
from .profile import TimingIndistinguishabilityProfile
from .projection import load_registry_server_trace, registry_timing_projection, relay_timing_projection


def _operation_ids(projection: dict[str, Any]) -> list[str]:
    return [str(item["operation_id"]) for item in projection["trajectory"]]


def run_protected_timing_workload(
    output: Path,
    workload: PrimaryTimingWorkload,
    profile: TimingIndistinguishabilityProfile,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite protected timing session: {output}")
    prewarm_framework(workload.framework)
    cases = list(workload.cases)
    native = run_online_framework_workflow(workload.framework, workload.workflow, cases, native_implementation)
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        canonical = run_online_framework_workflow(
            workload.framework,
            workload.workflow,
            cases,
            session.implementation(),
        )
    if session.trace is None:
        raise AssertionError("protected timing session did not expose its trace")
    trace = session.trace
    expected_all = [case.operation_id for case in cases]
    expected_external = [case.operation_id for case in cases if case.placement != "TRUSTED_MODULE_LOCAL"]
    canonical_agent_ids = [_canonical_ids(case)[0] for case in cases]
    expected_real_resolutions = len(set(canonical_agent_ids))
    expected_cache_hits = len(cases) - expected_real_resolutions
    pir = json.loads((output / "pir" / "online_query_summary.json").read_text(encoding="utf-8"))
    relay = relay_timing_projection(trace)
    registry = registry_timing_projection(
        load_registry_server_trace(output / "pir" / "server_visible_trace.jsonl"),
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
    )
    slots = [(int(item["session"]), int(item["round"])) for item in trace.get("public_relay_events", [])]
    causal = session.causal_proof()
    checks = {
        "native_exact_operations": _operation_ids(native["projection"]) == expected_all,
        "canonical_exact_operations": _operation_ids(canonical["projection"]) == expected_all,
        "level_a_semantic_projection": native["projection"] == canonical["projection"],
        "causal_proof": causal["passed"] is True,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "full_transcript": trace.get("public_transcript_complete") is True,
        "exact_cell_count": int(trace.get("emitted_cells", -1)) == profile.total_rounds,
        "exact_slot_order": slots == [(1, index) for index in range(1, profile.total_rounds + 1)],
        "no_duplicate_cells": len(slots) == len(set(slots)),
        "fixed_request_size": all(int(item["request_length"]) == 1079 for item in trace["public_relay_events"]),
        "fixed_response_size": all(int(item["response_length"]) == 800 for item in trace["public_relay_events"]),
        "accepted_ids": sorted(trace.get("accepted_operation_ids", [])) == sorted(expected_external),
        "result_ids": sorted(item["operation_id"] for item in trace.get("results", [])) == sorted(expected_external),
        "provider_count": int(trace.get("provider_invocations", -1)) == len(expected_external),
        "resolved_not_admitted": trace.get("resolved_not_admitted_ids", []) == [],
        "profile_overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "silent_result_loss": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "dummy_provider_operations": int(trace.get("dummy_provider_operations", -1)) == 0,
        "infrastructure_liveness": trace.get("infrastructure_liveness_failure") is False,
        "fixed_pir_count": int(pir["query_count"]) == 100,
        "pir_real_count": int(pir["real_query_count"]) == expected_real_resolutions,
        "pir_dummy_count": int(pir["dummy_query_count"]) == 100 - expected_real_resolutions,
        "descriptor_cache_hits": int(pir["descriptor_cache_hits"]) == expected_cache_hits,
        "no_secret_pir_bypass": int(pir.get("bypass_query_count", 0)) == 0,
    }
    failures = [name for name, passed in checks.items() if not passed]
    launches = trace.get("slot_launches", [])
    record = {
        "schema": "AgentTool.V12IsolatedProtectedTimingRecord/1",
        "identity": workload.identity,
        "task_id": workload.task_id,
        "task": workload.task,
        "framework": workload.framework,
        "label": workload.label,
        "block": workload.block,
        "stage": workload.stage,
        "profile_id": profile.profile_id,
        "delta_ms": profile.round_period_ms,
        "claim_observers": list(workload.claim_observers),
        "functional": not failures,
        "checks": checks,
        "failures": failures,
        "relay_projection": relay,
        "registry_projection": registry,
        "expected_real_resolutions": expected_real_resolutions,
        "expected_cache_hits": expected_cache_hits,
        "pir_summary": pir,
        "nominal_late_cells": int(trace.get("nominal_late_cells", 0)),
        "launch_slip_ns": [int(item.get("launch_slip_ns", 0)) for item in launches],
        "request_gap_ns": relay["request_inter_arrival_ns"],
        "response_gap_ns": relay["response_inter_arrival_ns"],
        "session_span_ns": relay["total_session_span_ns"],
        "pir_query_gap_ns": registry["inter_query_gap_ns"],
        "pir_query_response_ns": registry["query_response_ns"],
        "retry_count": 0,
        "replacement_count": 0,
    }
    (output / "isolated_timing_record.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return record
