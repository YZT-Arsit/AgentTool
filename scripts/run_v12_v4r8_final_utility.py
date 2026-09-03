from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_duplex_functional import build_workload
from scripts.run_v12_v4r7_bounded_liveness_functional import (
    _capacity_workflow_runner,
)
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import duplex_response_anchor_p10_profile
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)

RUNTIME_SOURCE = "63319014f560f46e2a46dd140f53551e43c27e0d"
EXPECTED_RUNNER_SHA256 = (
    "84fc61e363ed587ba5c200be12ebb66c9a71c69daad39950f1b50e66cd363437"
)
EXPECTED_PIR_SHA256 = "743684a35afcee942ff76810a091925ce9ca8eb21e33519c3748c694ef1c6f8c"
CSV_FIELDS = (
    "identity",
    "kind",
    "framework",
    "workload",
    "configuration",
    "repetition",
    "execution_order",
    "start_timestamp_ns",
    "semantic_completion_timestamp_ns",
    "end_timestamp_ns",
    "semantic_completion_ms",
    "public_session_wall_ms",
    "expected_operation_count",
    "executed_operation_count",
    "successful_provider_calls",
    "result_count",
    "semantic_result_equality",
    "causal_order_equality",
    "final_framework_state_equality",
    "relay_cell_count",
    "registry_query_count",
    "public_transcript_complete",
    "resolved_not_admitted",
    "silent_loss",
    "profile_overflow",
    "success",
    "failure_category",
    "retries",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def runner_for(workload: str):
    return (
        _capacity_workflow_runner
        if workload == "CAPACITY_50"
        else run_online_framework_workflow
    )


def normalized_expected(cases) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        outcome = native_implementation(case, case.arguments)
        rows.append(
            {
                "operation_id": case.operation_id,
                "logical_action": case.logical_action_name,
                "arguments": case.argument_schema.validate_values(case.arguments),
                "provider_visible_logical_request": outcome.provider_visible_logical_request,
                "effect_count": outcome.effect_count,
                "outcome": outcome.outcome_semantics,
                "result": outcome.result,
            }
        )
    return rows


def trajectory_equal(
    expected: list[dict[str, Any]], observed: list[dict[str, Any]]
) -> bool:
    fields = (
        "operation_id",
        "logical_action",
        "arguments",
        "provider_visible_logical_request",
        "effect_count",
        "outcome",
        "result",
    )
    return len(expected) == len(observed) and all(
        tuple(left[field] for field in fields)
        == tuple(right[field] for field in fields)
        for left, right in zip(expected, observed, strict=True)
    )


def validate_deployment(freeze: dict[str, Any]) -> dict[str, Any]:
    profile = duplex_response_anchor_p10_profile()
    frozen = freeze["profile"]
    checks = {
        "git_head_runtime_source": git("rev-parse", "HEAD") == RUNTIME_SOURCE,
        "profile_id": profile.profile_id == frozen["profile_id"],
        "R": profile.total_rounds == 521 == int(frozen["total_rounds"]),
        "Q": profile.pir_resolution_opportunities == 100,
        "H": profile.admission_horizon_ms == 4500,
        "B": profile.provider_completion_bound_ms == 200,
        "Delta": profile.round_period_ms == 10,
        "M": profile.maximum_real_operations == 50,
        "runner_sha256": sha256(
            ROOT
            / "common_action_gateway_v2"
            / "bin"
            / "canonical-v12-v4r8-timing-runner"
        )
        == EXPECTED_RUNNER_SHA256,
        "simplepir_sha256": sha256(
            ROOT / "pir_integration" / "simplepir_bridge" / "acv-simplepir-v12-timing"
        )
        == EXPECTED_PIR_SHA256,
        "benchmark_runner_sha256": sha256(Path(__file__).resolve())
        == freeze["source_hashes_before_freeze"]["benchmark_runner"],
    }
    result = {
        "schema": "AgentTool.V12V4R8FinalUtilityDeploymentGate/1",
        "runtime_source_commit": RUNTIME_SOURCE,
        "checks": checks,
        "pass": all(checks.values()),
        "protected_runtime_diff": "NONE" if all(checks.values()) else "GATE_FAILED",
        "classifier_runs": 0,
        "auc_calculations": 0,
    }
    if not result["pass"]:
        raise RuntimeError(f"V4R8 utility deployment gate failed: {checks}")
    return result


def run_native(row: dict[str, Any], unit_root: Path) -> dict[str, Any]:
    framework = str(row["framework"])
    workload = str(row["workload"])
    identity = str(row["identity"])
    workflow, cases = build_workload(workload, framework, identity)
    expected = normalized_expected(cases)
    prewarm_framework(framework)
    runner = runner_for(workload)
    start_timestamp_ns = time.time_ns()
    start_mono_ns = time.monotonic_ns()
    observed = runner(framework, workflow, cases, native_implementation)
    semantic_end_mono_ns = time.monotonic_ns()
    semantic_completion_timestamp_ns = time.time_ns()
    trajectory = list(observed["projection"]["trajectory"])
    expected_ids = [item["operation_id"] for item in expected]
    observed_ids = [item["operation_id"] for item in trajectory]
    final_expected = f"framework-completed:{workflow}"
    semantic_equal = trajectory_equal(expected, trajectory)
    causal_equal = observed_ids == expected_ids
    final_equal = observed["projection"]["final_framework_state"] == final_expected
    success = semantic_equal and causal_equal and final_equal
    result = {
        **row,
        "execution_order": row["pair_order"],
        "start_timestamp_ns": start_timestamp_ns,
        "semantic_completion_timestamp_ns": semantic_completion_timestamp_ns,
        "end_timestamp_ns": semantic_completion_timestamp_ns,
        "semantic_completion_ms": (semantic_end_mono_ns - start_mono_ns) / 1_000_000,
        "public_session_wall_ms": None,
        "expected_operation_count": len(cases),
        "executed_operation_count": len(trajectory),
        "successful_provider_calls": len(trajectory),
        "result_count": len(trajectory),
        "semantic_result_equality": semantic_equal,
        "causal_order_equality": causal_equal,
        "final_framework_state_equality": final_equal,
        "relay_cell_count": None,
        "registry_query_count": None,
        "public_transcript_complete": None,
        "resolved_not_admitted": None,
        "silent_loss": None,
        "profile_overflow": None,
        "success": success,
        "failure_category": "" if success else "NATIVE_SEMANTIC_MISMATCH",
        "retries": 0,
    }
    unit_root.mkdir(parents=True)
    (unit_root / "utility_record.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def run_oae(row: dict[str, Any], unit_root: Path) -> dict[str, Any]:
    framework = str(row["framework"])
    workload = str(row["workload"])
    identity = str(row["identity"])
    workflow, cases = build_workload(workload, framework, identity)
    expected = normalized_expected(cases)
    expected_ids = [item["operation_id"] for item in expected]
    prewarm_framework(framework)
    runner = runner_for(workload)
    profile = duplex_response_anchor_p10_profile()
    session_root = unit_root / "oae_session"
    unit_root.mkdir(parents=True)
    start_timestamp_ns = 0
    semantic_completion_timestamp_ns = 0
    semantic_ms = math.nan
    session: CanonicalOnlineSession
    with CanonicalOnlineSession(session_root, cases, public_profile=profile) as session:
        t0_mono_ns = next(
            int(item["monotonic_ns"])
            for item in session.lifecycle
            if item["stage"] == "SESSION_T0"
        )
        start_timestamp_ns = time.time_ns()
        semantic_start_mono_ns = time.monotonic_ns()
        observed = runner(framework, workflow, cases, session.implementation())
        semantic_end_mono_ns = time.monotonic_ns()
        semantic_completion_timestamp_ns = time.time_ns()
        semantic_ms = (semantic_end_mono_ns - semantic_start_mono_ns) / 1_000_000
    end_mono_ns = time.monotonic_ns()
    end_timestamp_ns = time.time_ns()
    if session.trace is None:
        raise RuntimeError("OAE V4R8 session closed without runtime trace")
    trace = session.trace
    trajectory = list(observed["projection"]["trajectory"])
    observed_ids = [item["operation_id"] for item in trajectory]
    relay = list(trace.get("public_relay_events", []))
    releases = list(trace.get("gateway_response_releases", []))
    registry_rows = load_registry_server_trace(
        session_root / "pir" / "server_visible_trace.jsonl"
    )
    relay_projection = relay_timing_projection(
        {"public_relay_events": relay},
        expected_rounds=521,
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
    semantic_equal = trajectory_equal(expected, trajectory)
    causal_equal = observed_ids == expected_ids
    final_equal = (
        observed["projection"]["final_framework_state"]
        == f"framework-completed:{workflow}"
    )
    structural = {
        "relay_cells": len(relay) == 521,
        "relay_slots": sorted(int(item["round"]) for item in relay)
        == list(range(1, 522)),
        "registry_queries": len(registry_rows) == 100,
        "registry_ordinals": sorted(int(item["ordinal"]) for item in registry_rows)
        == list(range(100)),
        "relay_projection": relay_projection["view"] == DUPLEX_TIMING_ONLY_VIEW,
        "registry_projection": registry_projection["view"] == "TIMING_ONLY_VIEW",
        "release_inventory": len(releases) == 521,
        "release_attempts": all(
            bool(item.get("release_attempted")) for item in releases
        ),
        "successful_writes": all(
            bool(item.get("response_write_completed")) for item in releases
        ),
        "fixed_request_bytes": all(
            int(item["request_length"]) == 1079 for item in relay
        ),
        "fixed_response_bytes": all(
            int(item["response_length"]) == 800 for item in relay
        ),
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "runtime_complete": trace.get("session_status") == "COMPLETE",
        "no_infrastructure_failure": trace.get("infrastructure_liveness_failure")
        is False,
    }
    results = list(trace.get("results", []))
    providers = list(trace.get("provider_diagnostics", []))
    provider_success = sum(item.get("class") == "PROVIDER_OK" for item in providers)
    resolved_not_admitted = len(trace.get("resolved_not_admitted_ids", []))
    silent_loss = int(trace.get("silent_committed_result_losses", -1))
    overflow = int(trace.get("profile_overflow_events", -1))
    success = (
        semantic_equal
        and causal_equal
        and final_equal
        and all(structural.values())
        and provider_success == len(cases)
        and len(results) == len(cases)
        and resolved_not_admitted == 0
        and silent_loss == 0
        and overflow == 0
    )
    result = {
        **row,
        "execution_order": row["pair_order"],
        "start_timestamp_ns": start_timestamp_ns,
        "semantic_completion_timestamp_ns": semantic_completion_timestamp_ns,
        "end_timestamp_ns": end_timestamp_ns,
        "semantic_completion_ms": semantic_ms,
        "public_session_wall_ms": (end_mono_ns - t0_mono_ns) / 1_000_000,
        "expected_operation_count": len(cases),
        "executed_operation_count": len(trajectory),
        "successful_provider_calls": provider_success,
        "result_count": len(results),
        "semantic_result_equality": semantic_equal,
        "causal_order_equality": causal_equal,
        "final_framework_state_equality": final_equal,
        "relay_cell_count": len(relay),
        "registry_query_count": len(registry_rows),
        "public_transcript_complete": trace.get("public_transcript_complete"),
        "resolved_not_admitted": resolved_not_admitted,
        "silent_loss": silent_loss,
        "profile_overflow": overflow,
        "registry_query_bytes": sorted(
            {int(item["query_bytes"]) for item in registry_rows}
        ),
        "registry_answer_bytes": sorted(
            {int(item["answer_bytes"]) for item in registry_rows}
        ),
        "response_deadline_misses": sum(
            bool(item.get("deadline_miss")) for item in releases
        ),
        "maximum_response_release_slip_ns": max(
            (int(item.get("release_slip_ns", 0)) for item in releases), default=0
        ),
        "structural_checks": structural,
        "success": success,
        "failure_category": "" if success else "OAE_FUNCTIONAL_OR_TRANSCRIPT_FAILURE",
        "retries": 0,
    }
    (unit_root / "utility_record.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires data")
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for workload in (
            "ORDINARY_TOOL",
            "AGENT_AS_TOOL_TRANSITION",
            "CACHE_REUSE_30",
            "CAPACITY_50",
        ):
            grouped: dict[str, dict[str, Any]] = {}
            for configuration in ("NATIVE", "OAE_V4R8"):
                selected = [
                    item
                    for item in records
                    if item["framework"] == framework
                    and item["workload"] == workload
                    and item["configuration"] == configuration
                ]
                # Failed runs have no final expected semantic-result boundary.
                # They remain in N/failure counts and raw evidence; latency
                # summaries explicitly use successful, finite observations.
                semantic = [
                    float(item["semantic_completion_ms"])
                    for item in selected
                    if item["success"]
                    and item["semantic_completion_ms"] is not None
                    and math.isfinite(float(item["semantic_completion_ms"]))
                ]
                public = [
                    float(item["public_session_wall_ms"])
                    for item in selected
                    if item["success"] and item["public_session_wall_ms"] is not None
                ]
                if not semantic:
                    raise RuntimeError(
                        "no successful latency observations for "
                        f"{framework}/{workload}/{configuration}"
                    )
                grouped[configuration] = {
                    "N": len(selected),
                    "successes": sum(bool(item["success"]) for item in selected),
                    "failures": sum(not bool(item["success"]) for item in selected),
                    "success_rate": sum(bool(item["success"]) for item in selected)
                    / len(selected),
                    "semantic_latency_sample_N": len(semantic),
                    "semantic_median_ms": statistics.median(semantic),
                    "semantic_p95_ms": percentile(semantic, 0.95),
                    "semantic_mean_ms": statistics.mean(semantic),
                    "semantic_std_ms": statistics.stdev(semantic),
                    "semantic_min_ms": min(semantic),
                    "semantic_max_ms": max(semantic),
                    "public_session_latency_sample_N": len(public),
                    "public_session_median_ms": statistics.median(public)
                    if public
                    else None,
                    "public_session_p95_ms": percentile(public, 0.95)
                    if public
                    else None,
                }
            native_median = grouped["NATIVE"]["semantic_median_ms"]
            oae_median = grouped["OAE_V4R8"]["semantic_median_ms"]
            for configuration in ("NATIVE", "OAE_V4R8"):
                row = {
                    "framework": framework,
                    "workload": workload,
                    "configuration": configuration,
                    **grouped[configuration],
                    "additive_overhead_ms": oae_median - native_median,
                    "multiplicative_overhead": oae_median / native_median,
                }
                rows.append(row)
    return rows


def write_csv(
    path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...] | None = None
) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV")
    names = list(fields or tuple(rows[0].keys()))
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite utility output: {args.output}")
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    if freeze.get("frozen_before_execution") is not True:
        raise ValueError("utility schedule is not frozen")
    schedule = list(freeze["schedule"])
    if len(schedule) != 512 or len({item["identity"] for item in schedule}) != 512:
        raise ValueError("frozen utility schedule is malformed")
    args.output.mkdir(parents=True)
    deployment = validate_deployment(freeze)
    (args.output / "deployment_gate.json").write_text(
        json.dumps(deployment, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    records: list[dict[str, Any]] = []
    warmups: list[dict[str, Any]] = []
    ledger_path = args.output / "execution_ledger.jsonl"
    previous_hash = "0" * 64
    for row in schedule:
        unit_root = (
            args.output / "runs" / f"{int(row['ordinal']):04d}_{row['identity']}"
        )
        try:
            result = (
                run_native(row, unit_root)
                if row["configuration"] == "NATIVE"
                else run_oae(row, unit_root)
            )
        except Exception as error:  # noqa: BLE001 - every frozen observation is retained
            result = {
                **row,
                "execution_order": row["pair_order"],
                "start_timestamp_ns": None,
                "semantic_completion_timestamp_ns": None,
                "end_timestamp_ns": time.time_ns(),
                "semantic_completion_ms": math.nan,
                "public_session_wall_ms": None,
                "expected_operation_count": None,
                "executed_operation_count": None,
                "successful_provider_calls": None,
                "result_count": None,
                "semantic_result_equality": False,
                "causal_order_equality": False,
                "final_framework_state_equality": False,
                "relay_cell_count": None,
                "registry_query_count": None,
                "public_transcript_complete": False,
                "resolved_not_admitted": None,
                "silent_loss": None,
                "profile_overflow": None,
                "success": False,
                "failure_category": type(error).__name__,
                "exception_string": str(error),
                "traceback": traceback.format_exc(),
                "retries": 0,
            }
            unit_root.mkdir(parents=True, exist_ok=True)
            (unit_root / "utility_record.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
            )
        target = warmups if row["kind"] == "WARMUP" else records
        target.append(result)
        ledger_record = {
            "ordinal": row["ordinal"],
            "identity": row["identity"],
            "kind": row["kind"],
            "success": result["success"],
            "failure_category": result["failure_category"],
            "previous_sha256": previous_hash,
            "retries": 0,
        }
        encoded = json.dumps(
            ledger_record, sort_keys=True, separators=(",", ":")
        ).encode()
        previous_hash = hashlib.sha256(encoded).hexdigest()
        ledger_record["record_sha256"] = previous_hash
        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(ledger_record, sort_keys=True) + "\n")
        with (args.output / "progress.json").open(
            "w", encoding="utf-8", newline="\n"
        ) as handle:
            json.dump(
                {
                    "planned_total": 512,
                    "executed_total": len(warmups) + len(records),
                    "warmups_executed": len(warmups),
                    "measured_executed": len(records),
                    "last_identity": row["identity"],
                    "last_success": result["success"],
                    "classifier_runs": 0,
                    "auc_calculations": 0,
                },
                handle,
                indent=2,
            )
            handle.write("\n")
    if len(records) != 480 or len(warmups) != 32:
        raise AssertionError("utility execution denominator did not close")
    summary_rows = summaries(records)
    write_csv(args.output / "final_utility_runs.csv", records, CSV_FIELDS)
    write_csv(args.output / "final_utility_summary.csv", summary_rows)
    with (args.output / "warmup_runs.jsonl").open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        for row in warmups:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    completion = {
        "schema": "AgentTool.V12V4R8FinalUtilityCompletion/1",
        "freeze_sha256": sha256(args.freeze),
        "planned_warmups": 32,
        "executed_warmups": len(warmups),
        "planned_measured_executions": 480,
        "executed_measured_executions": len(records),
        "native_successes": sum(
            item["configuration"] == "NATIVE" and bool(item["success"])
            for item in records
        ),
        "native_failures": sum(
            item["configuration"] == "NATIVE" and not bool(item["success"])
            for item in records
        ),
        "oae_successes": sum(
            item["configuration"] == "OAE_V4R8" and bool(item["success"])
            for item in records
        ),
        "oae_failures": sum(
            item["configuration"] == "OAE_V4R8" and not bool(item["success"])
            for item in records
        ),
        "oae_transcript_successes": sum(
            item["configuration"] == "OAE_V4R8"
            and item["public_transcript_complete"] is True
            and item["relay_cell_count"] == 521
            and item["registry_query_count"] == 100
            for item in records
        ),
        "oae_silent_losses": sum(
            int(item["silent_loss"] or 0)
            for item in records
            if item["configuration"] == "OAE_V4R8"
        ),
        "oae_profile_overflows": sum(
            int(item["profile_overflow"] or 0)
            for item in records
            if item["configuration"] == "OAE_V4R8"
        ),
        "retries": 0,
        "classifier_runs": 0,
        "auc_calculations": 0,
        "summary_rows": summary_rows,
    }
    (args.output / "completion.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
