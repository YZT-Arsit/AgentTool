from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from v11_full_scope.canonical import native_local_outcome
from v11_full_scope.models import V11ActionCase
from v11_online.frameworks import (
    prewarm_framework,
    run_online_framework_workflow,
    trajectory_projection,
)
from v11_online.session import CanonicalOnlineSession

from .profile import OnlinePublicProfile


def _native_implementation(case: V11ActionCase, _arguments: dict[str, Any]):
    return native_local_outcome(case)


def _trace_checks(trace: dict[str, Any], profile: OnlinePublicProfile, expected_external: int) -> dict[str, Any]:
    events = list(trace.get("public_relay_events", []))
    result_ids = [str(item["operation_id"]) for item in trace.get("results", [])]
    client_connections = len({str(event["relay_client_connection_id"]) for event in events})
    gateway_connections = len({str(event["relay_gateway_connection_id"]) for event in events})
    setup = [str(event["stage"]) for event in trace.get("public_setup_events", [])]
    checks = {
        "session_complete": trace.get("session_status") == "COMPLETE",
        "online_mode": trace.get("online_mode") is True,
        "startup_action_count_zero": int(trace.get("startup_action_count", -1)) == 0,
        "admitted_expected": int(trace.get("admitted", -1)) == expected_external,
        "result_count_expected": len(result_ids) == expected_external,
        "result_ids_unique": len(result_ids) == len(set(result_ids)),
        "provider_invocations_expected": int(trace.get("provider_invocations", -1)) == expected_external,
        "dummy_heavy_ops_zero": int(trace.get("dummy_provider_operations", -1)) == 0,
        "profile_overflow_zero": int(trace.get("profile_overflow_events", -1)) == 0,
        "scheduler_miss_zero": int(trace.get("schedule_misses", -1)) == 0,
        "silent_committed_result_loss_zero": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "pending_empty": not trace.get("pending_operation_ids", []),
        "resolved_not_admitted_empty": not trace.get("resolved_not_admitted_ids", []),
        "unresolved_empty": not trace.get("unresolved_operation_ids", []),
        "framework_waiters_empty": not trace.get("framework_waiter_ids", []),
        "exact_round_count": len(events) == profile.total_rounds,
        "exact_round_order": [int(event["round"]) for event in events] == list(range(1, profile.total_rounds + 1)),
        "exact_request_sizes": {int(event["request_length"]) for event in events} == {profile.request_final_bytes},
        "exact_response_sizes": {int(event["response_length"]) for event in events} == {profile.response_final_bytes},
        "one_client_relay_connection": client_connections == 1,
        "one_relay_gateway_connection": gateway_connections == 1,
        "http2_client_relay": all(event.get("client_http_version") == "HTTP/2.0" for event in events),
        "http2_relay_gateway": all(event.get("gateway_http_version") == "HTTP/2.0" for event in events),
        "single_preconnect_each_hop": setup.count("CLIENT_RELAY_HTTP2_ESTABLISHED") == 1 and setup.count("RELAY_GATEWAY_HTTP2_ESTABLISHED") == 1,
        "fixed_ohttp_suite": all(
            (
                int(event.get("ohttp_key_id", -1)) == profile.ohttp_key_id,
                int(event.get("kem_id", -1)) == profile.kem_id,
                int(event.get("kdf_id", -1)) == profile.kdf_id,
                int(event.get("aead_id", -1)) == profile.aead_id,
                int(event.get("config_epoch", -1)) == profile.config_epoch,
            )
            for event in events
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "rounds": len(events),
        "client_relay_connections": client_connections,
        "relay_gateway_connections": gateway_connections,
        "schedule_misses": int(trace.get("schedule_misses", -1)),
        "profile_overflow": int(trace.get("profile_overflow_events", -1)),
        "dummy_heavy_ops": int(trace.get("dummy_provider_operations", -1)),
        "silent_committed_result_loss": int(trace.get("silent_committed_result_losses", -1)),
        "session_status": str(trace.get("session_status", "MISSING")),
        "resolved_not_admitted": len(trace.get("resolved_not_admitted_ids", [])),
    }


def run_online_development(
    output: Path,
    framework: str,
    workflow: str,
    cases: list[V11ActionCase],
    runner: Path,
    profile: OnlinePublicProfile,
    *,
    compare_native: bool = False,
    require_strict_causal: bool = True,
    pir_delay_ms: int = 0,
    decision_delay_ms: int = 0,
) -> dict[str, Any]:
    """Execute one non-holdout development session exactly once."""

    if output.exists():
        raise FileExistsError(f"refusing to retry or overwrite development evidence: {output}")
    started = time.monotonic()
    profile.validate()
    prewarm_framework(framework)
    native: dict[str, Any] | None = None
    session: CanonicalOnlineSession | None = None
    canonical: dict[str, Any] | None = None
    error = ""
    try:
        if compare_native:
            native = run_online_framework_workflow(framework, workflow, cases, _native_implementation)
        session = CanonicalOnlineSession(
            output,
            cases,
            runner_binary=runner,
            public_profile=profile,
            pir_delay_ms=pir_delay_ms,
            decision_delay_ms=decision_delay_ms,
        )
        with session:
            canonical = run_online_framework_workflow(framework, workflow, cases, session.implementation())
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    trace: dict[str, Any] = {}
    if session is not None and session.trace is not None:
        trace = session.trace
    elif (output / "go_online_result.json").is_file():
        trace = json.loads((output / "go_online_result.json").read_text(encoding="utf-8"))
    expected_external = sum(case.placement == "EXTERNAL" for case in cases)
    trace_gate = _trace_checks(trace, profile, expected_external) if trace else {
        "checks": {}, "passed": False, "rounds": 0, "client_relay_connections": 0,
        "relay_gateway_connections": 0, "schedule_misses": -1, "profile_overflow": -1,
        "dummy_heavy_ops": -1, "silent_committed_result_loss": -1,
        "session_status": "NO_TRACE", "resolved_not_admitted": -1,
    }
    causal = session.causal_proof() if session is not None else {"passed": False, "checks": []}
    semantic_equal = not compare_native or (
        native is not None and canonical is not None and native["projection"] == canonical["projection"]
    )
    dynamic_pir = bool(
        session is not None
        and session.pir is not None
        and session.pir.query_count == len(cases)
        and len(session.pir.query_hashes) == len(set(session.pir.query_hashes))
    )
    passed = bool(
        not error
        and trace_gate["passed"]
        and dynamic_pir
        and semantic_equal
        and (causal.get("passed") if require_strict_causal else True)
    )
    structural = size = None
    if session is not None and session.trace is not None:
        try:
            structural, size = session.public_projections()
        except Exception as exc:
            if not error:
                error = f"{type(exc).__name__}: {exc}"
            passed = False
    value = {
        "passed": passed,
        "error": error,
        "framework": framework,
        "workflow": workflow,
        "profile_id": profile.profile_id,
        "admission_rounds": profile.admission_rounds,
        "admission_horizon_ms": profile.admission_horizon_ms,
        "total_rounds_expected": profile.total_rounds,
        "scheduled_lifetime_ms": profile.scheduled_lifetime_ms,
        "logical_actions": len(cases),
        "external_actions": expected_external,
        "pir_delay_ms": pir_delay_ms,
        "decision_delay_ms": decision_delay_ms,
        "dynamic_pir": dynamic_pir,
        "causal_proof": causal,
        "semantic_equal": semantic_equal,
        "trace_gate": trace_gate,
        "public_session_count": 1 if trace else 0,
        "strict_structural_projection": structural,
        "strict_size_projection": size,
        "canonical_projection": canonical["projection"] if canonical is not None else None,
        "native_projection": native["projection"] if native is not None else None,
        "elapsed_seconds": time.monotonic() - started,
        "holdout": False,
        "selected_v10_or_v10_1_case": False,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "v11_3_development_summary.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return value


def direct_native_projection(cases: list[V11ActionCase], workflow: str) -> dict[str, Any]:
    outcomes = [native_local_outcome(case) for case in cases]
    return trajectory_projection(cases, outcomes, f"framework-completed:{workflow}")
