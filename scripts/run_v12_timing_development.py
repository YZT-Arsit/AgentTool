from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.fixtures import tool_case
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.matrix import TimingWorkflow, frozen_order
from v12_timing.profile import TimingIndistinguishabilityProfile
from v12_timing.projection import load_registry_server_trace, registry_timing_projection, relay_timing_projection


MATRIX_PATH = ROOT / "V12_TIMING_DEVELOPMENT_MATRIX.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _control_projection(observer: str, label: int, *, rounds: int, period_ms: int) -> dict[str, Any]:
    # Fresh unprotected control: work duration is deliberately secret-dependent.
    # The label is never embedded in the feature record; it is stored only as the
    # supervised target alongside the projection.
    count = rounds
    delay_ns = 100_000 if label == 0 else 2_000_000
    probe_start = time.perf_counter_ns()
    work_until = probe_start + delay_ns
    while time.perf_counter_ns() < work_until:
        pass
    measured_work_ns = time.perf_counter_ns() - probe_start
    start = time.perf_counter_ns()
    timestamps = [start + ordinal * period_ms * 1_000_000 for ordinal in range(count)]
    responses = [value + measured_work_ns for value in timestamps]
    if observer == "RELAY":
        events = [
            {
                "profile_id": "UNPROTECTED-DIRECT-TIMING-CONTROL",
                "session": 1,
                "round": ordinal + 1,
                "request_length": 1079,
                "response_length": 800,
                "relay_endpoint": "DIRECT_CONTROL",
                "gateway_endpoint": "DIRECT_CONTROL",
                "request_observed_ns": timestamps[ordinal],
                "response_observed_ns": responses[ordinal],
                "client_http_version": "HTTP/2.0",
                "gateway_http_version": "HTTP/2.0",
            }
            for ordinal in range(count)
        ]
        return relay_timing_projection({"public_relay_events": events})
    rows = [
        {
            "ordinal": ordinal,
            "query_bytes": 2020,
            "query_rows": 501,
            "query_cols": 1,
            "answer_bytes": 6592,
            "executor": "SimplePIRServer-UNPROTECTED-CONTROL",
            "request_kind": "DIRECT_PIR_CONTROL",
            "request_arrival_ns": timestamps[ordinal],
            "answer_ready_ns": responses[ordinal],
        }
        for ordinal in range(count)
    ]
    return registry_timing_projection(
        rows,
        profile_id="UNPROTECTED-DIRECT-TIMING-CONTROL",
        pir_period_ms=period_ms,
        opportunities=count,
    )


def _functional(
    trace: dict[str, Any],
    expected_ids: list[str],
    rounds: int,
    *,
    expected_provider_count: int,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    events = trace.get("public_relay_events", [])
    slots = [(int(item["session"]), int(item["round"])) for item in events]
    checks = {
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "emitted_cells": int(trace.get("emitted_cells", -1)) == rounds,
        "event_count": len(events) == rounds,
        "exact_slot_order": slots == [(1, index) for index in range(1, rounds + 1)],
        "unique_slots": len(slots) == len(set(slots)),
        "request_sizes": all(int(item["request_length"]) == 1079 for item in events),
        "response_sizes": all(int(item["response_length"]) == 800 for item in events),
        "accepted_ids": sorted(trace.get("accepted_operation_ids", [])) == sorted(expected_ids),
        "result_ids": sorted(item["operation_id"] for item in trace.get("results", [])) == sorted(expected_ids),
        "provider_count": int(trace.get("provider_invocations", -1)) == expected_provider_count,
        "dummy_heavy": int(trace.get("dummy_provider_operations", -1)) == 0,
        "overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "silent_loss": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "liveness": trace.get("infrastructure_liveness_failure") is False,
    }
    for name, passed in checks.items():
        if not passed:
            failures.append(name)
    return not failures, failures


def _run_capacity(output: Path, period: int, profile: TimingIndistinguishabilityProfile) -> None:
    framework = "OpenAI Agents SDK"
    cases = [
        replace(
            tool_case(f"DEV-TD-CAPACITY50-P{period}-A{index:02d}", framework),
            operation_id=f"opTDC{period:02d}{index:02d}",
            logical_action_name=f"capacity_tool_{index}",
        ).validate()
        for index in range(50)
    ]
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        run_online_framework_workflow(framework, "DYNAMIC_SEQUENCE", cases, session.implementation())
    assert session.trace is not None
    passed, failures = _functional(
        session.trace,
        [case.operation_id for case in cases],
        profile.total_rounds,
        expected_provider_count=len(cases),
    )
    summary = json.loads((output / "pir" / "online_query_summary.json").read_text(encoding="utf-8"))
    if summary["query_count"] != 50 or summary["real_query_count"] != 50 or summary["dummy_query_count"] != 0:
        failures.append("capacity_50_fixed_pir_schedule")
    record = {"identity": f"DEV-TD-CAPACITY50-P{period}-PIR60", "passed": passed and not failures, "failures": failures, "pir": summary}
    (output / "capacity_verdict.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not record["passed"]:
        raise RuntimeError(f"capacity gate failed: {record}")


def _run_workflow(output: Path, item: TimingWorkflow, profile: TimingIndistinguishabilityProfile) -> dict[str, Any]:
    native = run_online_framework_workflow(item.framework, item.workflow, list(item.cases), native_implementation)
    with CanonicalOnlineSession(output, list(item.cases), public_profile=profile) as session:
        canonical = run_online_framework_workflow(item.framework, item.workflow, list(item.cases), session.implementation())
    assert session.trace is not None
    semantic_equal = native["projection"] == canonical["projection"]
    causal = session.causal_proof()
    functional, failures = _functional(
        session.trace,
        [case.operation_id for case in item.cases if case.placement != "TRUSTED_MODULE_LOCAL"],
        profile.total_rounds,
        expected_provider_count=sum(case.placement != "TRUSTED_MODULE_LOCAL" for case in item.cases),
    )
    if not semantic_equal:
        failures.append("native_canonical_semantic_projection")
    if not causal["passed"]:
        failures.append("causal_proof")
    registry = registry_timing_projection(
        load_registry_server_trace(output / "pir" / "server_visible_trace.jsonl"),
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
    )
    relay = relay_timing_projection(session.trace)
    record = {
        "workflow_id": item.workflow_id,
        "secret_labels": item.labels,
        "block": item.block,
        "orthogonal_row": item.orthogonal_row,
        "framework": item.framework,
        "profile_id": profile.profile_id,
        "functional": functional and semantic_equal and causal["passed"],
        "failures": failures,
        "relay_projection": relay,
        "registry_projection": registry,
        "positive_controls": {
            task: {
                "RELAY": _control_projection("RELAY", label, rounds=16, period_ms=1),
                "REGISTRY": _control_projection("REGISTRY", label, rounds=16, period_ms=1),
            }
            for task, label in item.labels.items()
        },
        "lateness": {
            "nominal_late_cells": session.trace.get("nominal_late_cells", 0),
            "maximum_launch_slip_ns": max((int(value.get("launch_slip_ns", 0)) for value in session.trace.get("slot_launches", [])), default=0),
            "total_session_span_ns": relay["total_session_span_ns"],
        },
    }
    (output / "timing_record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--period", type=int, choices=(10, 20, 25), required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite timing development root: {args.output}")
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True)
    profile = TimingIndistinguishabilityProfile(
        profile_id=f"V12-TIMING-INDIST-H50-H3000-P{args.period}-PIR60",
        round_period_ms=args.period,
        pir_resolution_period_ms=60,
    ).validate()
    campaign = {
        "schema": "AgentTool.V12TimingDevelopmentCampaign/1",
        "matrix_sha256": _sha(MATRIX_PATH),
        "period_ms": args.period,
        "pir_period_ms": 60,
        "process_id": os.getpid(),
        "started_ns": time.time_ns(),
        "expected_sessions": matrix["sessions_per_profile"],
        "completed_sessions": 0,
    }
    (args.output / "campaign_manifest.json").write_text(json.dumps(campaign, indent=2) + "\n", encoding="utf-8")
    _run_capacity(args.output / "capacity50", args.period, profile)
    rows = frozen_order(
        profile_period=args.period,
        blocks=int(matrix["blocks_per_profile"]),
        seed_hex=str(matrix["randomization_seed_sha256"]),
    )
    ledger = args.output / "execution_ledger.jsonl"
    previous = "0" * 64
    for index, item in enumerate(rows):
        session_output = args.output / "sessions" / f"{index:04d}_{item.workflow_id}"
        started = time.time_ns()
        record = _run_workflow(session_output, item, profile)
        ledger_record = {
            "index": index,
            "workflow_id": item.workflow_id,
            "secret_labels": item.labels,
            "block": item.block,
            "started_ns": started,
            "ended_ns": time.time_ns(),
            "functional": record["functional"],
            "record_path": str((session_output / "timing_record.json").relative_to(args.output)),
            "record_sha256": _sha(session_output / "timing_record.json"),
            "previous_record_sha256": previous,
        }
        encoded = json.dumps(ledger_record, sort_keys=True, separators=(",", ":"))
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
        previous = hashlib.sha256(encoded.encode()).hexdigest()
        campaign["completed_sessions"] = index + 1
        campaign["last_ledger_record_sha256"] = previous
        if not record["functional"]:
            campaign["status"] = "FUNCTIONAL_FAILURE"
            (args.output / "campaign_failure.json").write_text(json.dumps(campaign | {"failure": record}, indent=2) + "\n", encoding="utf-8")
            return 2
    campaign["status"] = "COMPLETE"
    campaign["ended_ns"] = time.time_ns()
    campaign["ledger_sha256"] = _sha(ledger)
    (args.output / "campaign_completion.json").write_text(json.dumps(campaign, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
