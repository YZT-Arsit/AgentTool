from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_3_profile_closure import execute_once, strict_cases
from scripts.run_v12_performance import (
    COUNTS,
    PROFILE,
    REPS,
    canonical_boundary_latency_ms,
    cpu_clock_ns,
    native_bytes,
    pir_bytes,
    row,
    rss_bytes,
)
from v11_online.session import OnlineSimplePIRResolver


STRICT_BASELINES = (
    "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL",
    "B5_FULL_STRICT",
)


def append_record(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def classified(value: dict[str, Any]) -> tuple[str, int, int]:
    gate = value.get("trace_gate", {})
    if value.get("passed"):
        return "PASS", int(gate.get("schedule_misses", 0)), int(gate.get("rounds", 0))
    status = str(gate.get("session_status", "CANONICAL_FUNCTIONAL_FAIL"))
    return status, int(gate.get("schedule_misses", 0)), int(gate.get("rounds", 0))


def enrich(
    value: dict[str, Any],
    *,
    status: str = "PASS",
    functional: bool = True,
    schedule_misses: int = 0,
    rounds_observed: int | str = "",
    source_evidence: str,
    error: str = "",
) -> dict[str, Any]:
    value.update(
        status_class=status,
        functional=functional,
        schedule_misses=schedule_misses,
        rounds_observed=rounds_observed,
        source_evidence=source_evidence,
        error=error,
    )
    return value


def unavailable_resource(value: dict[str, Any]) -> dict[str, Any]:
    value["cpu_ms"] = ""
    value["peak_rss_bytes"] = ""
    return value


def rerun_non_strict(
    output: Path,
    go_bench: Path,
    journal: Path,
    completed: set[tuple[str, int, int]],
) -> None:
    # The interrupted campaign kept no per-repetition B0-B3 metrics in its
    # process memory.  These are new, separately identified repetitions; no
    # strict/failing session is retried or overwritten.
    for count in COUNTS:
        for rep in range(REPS):
            identity = ("B0_DIRECT_NATIVE", count, rep)
            if identity in completed:
                continue
            cases = strict_cases(count, f"DEV-V12-PERF-RECOVERY-B0-C{count}-R{rep}")
            c0 = cpu_clock_ns()
            t0 = time.monotonic_ns()
            sent, received = native_bytes(cases)
            wall = time.monotonic_ns() - t0
            append_record(
                journal,
                enrich(
                    row(
                        "B0_DIRECT_NATIVE",
                        count,
                        rep,
                        wall,
                        cpu_clock_ns() - c0,
                        sent,
                        received,
                        rss_bytes(),
                    ),
                    source_evidence="RECOVERY_NEW_REPETITION_AFTER_INTERRUPTED_IN_MEMORY_METRICS",
                ),
            )
            completed.add(identity)
    for count in COUNTS:
        if all(("B1_PIR_PLUS_DIRECT_ACTION", count, rep) in completed for rep in range(REPS)):
            continue
        with OnlineSimplePIRResolver(output / f"b1_pir_c{count}", record_count=64) as resolver:
            for rep in range(REPS):
                identity = ("B1_PIR_PLUS_DIRECT_ACTION", count, rep)
                if identity in completed:
                    continue
                cases = strict_cases(count, f"DEV-V12-PERF-RECOVERY-B1-C{count}-R{rep}")
                pid = resolver.process.pid if resolver.process is not None else -1
                before = pir_bytes(resolver.output)
                c0 = cpu_clock_ns(pid)
                t0 = time.monotonic_ns()
                for case in cases:
                    resolver.query(case.operation_id, case.agent_id)
                sent, received = native_bytes(cases)
                wall = time.monotonic_ns() - t0
                after = pir_bytes(resolver.output)
                append_record(
                    journal,
                    enrich(
                        row(
                            "B1_PIR_PLUS_DIRECT_ACTION",
                            count,
                            rep,
                            wall,
                            cpu_clock_ns(pid) - c0,
                            sent,
                            received,
                            rss_bytes(),
                            after[0] - before[0],
                            after[1] - before[1],
                        ),
                        source_evidence="RECOVERY_NEW_REPETITION_AFTER_INTERRUPTED_IN_MEMORY_METRICS",
                    ),
                )
                completed.add(identity)
    for mode, baseline in (
        ("B2", "B2_PIR_PLUS_OHTTP_UNSHAPED"),
        ("B3", "B3_PIR_PLUS_OHTTP_PADDED"),
    ):
        for count in COUNTS:
            if all((baseline, count, rep) in completed for rep in range(REPS)):
                continue
            with OnlineSimplePIRResolver(
                output / f"{mode.lower()}_pir_c{count}", record_count=64
            ) as resolver:
                for rep in range(REPS):
                    identity = (baseline, count, rep)
                    if identity in completed:
                        continue
                    pid = resolver.process.pid if resolver.process is not None else -1
                    before = pir_bytes(resolver.output)
                    c0 = cpu_clock_ns(pid)
                    t0 = time.monotonic_ns()
                    for query_number in range(count):
                        resolver.query(
                            f"v12-recovery-{mode}-c{count}-r{rep}-q{query_number}", 10
                        )
                    measured = json.loads(
                        subprocess.check_output(
                            [str(go_bench), "--mode", mode, "--count", str(count)],
                            text=True,
                        )
                    )
                    wall = time.monotonic_ns() - t0
                    checks = (
                        int(measured.get("relay_requests", -1)) == count,
                        int(measured.get("gateway_requests", -1)) == count,
                        int(measured.get("provider_invocations", -1)) == count,
                        int(measured.get("dummy_provider_operations", -1)) == 0,
                        int(measured.get("relay_connections", 0)) >= 1,
                        int(measured.get("gateway_connections", 0)) >= 1,
                        measured.get("relay_exact_forwarding") is True,
                    )
                    if not all(checks):
                        raise RuntimeError(f"{mode} local Relay/Gateway/provider recovery path failed")
                    after = pir_bytes(resolver.output)
                    append_record(
                        journal,
                        enrich(
                            row(
                                baseline,
                                count,
                                rep,
                                wall,
                                cpu_clock_ns(pid) - c0,
                                int(measured["bytes_sent"]),
                                int(measured["bytes_received"]),
                                int(measured["peak_rss_bytes"]),
                                after[0] - before[0],
                                after[1] - before[1],
                                latency_boundary="OHTTP_CLIENT_DECAPSULATION",
                            ),
                            source_evidence="RECOVERY_NEW_REPETITION_AFTER_INTERRUPTED_IN_MEMORY_METRICS",
                        ),
                    )
                    completed.add(identity)


def reconstruct_or_continue_strict(
    failed_root: Path,
    output: Path,
    runner: Path,
    journal: Path,
    completed: set[tuple[str, int, int]],
) -> None:
    for baseline in STRICT_BASELINES:
        for count in COUNTS:
            for rep in range(REPS):
                identity = (baseline, count, rep)
                if identity in completed:
                    continue
                old = failed_root / "strict_raw" / baseline / f"c{count}" / f"{rep:02d}"
                new = output / "strict_continuation" / baseline / f"c{count}" / f"{rep:02d}"
                if old.exists():
                    summary = json.loads(
                        (old / "v11_3_development_summary.json").read_text(encoding="utf-8")
                    )
                    status, misses, rounds = classified(summary)
                    sizes = summary.get("strict_size_projection") or {}
                    sent = sum(sizes.get("request_final_bytes", []))
                    received = sum(sizes.get("response_final_bytes", []))
                    p_sent, p_received = pir_bytes(old / "pir")
                    action_latency: float | str = ""
                    try:
                        action_latency = canonical_boundary_latency_ms(old)
                    except (AssertionError, FileNotFoundError, KeyError):
                        pass
                    append_record(
                        journal,
                        enrich(
                            unavailable_resource(row(
                                baseline,
                                count,
                                rep,
                                int(float(summary.get("elapsed_seconds", 0)) * 1_000_000_000),
                                0,
                                sent,
                                received,
                                0,
                                p_sent,
                                p_received,
                                action_latency_ms=action_latency,
                                latency_boundary="CANONICAL_FRAMEWORK_RESULT",
                            )),
                            status=status,
                            functional=bool(summary.get("passed")),
                            schedule_misses=misses,
                            rounds_observed=rounds,
                            source_evidence="IMMUTABLE_INTERRUPTED_CAMPAIGN_RECONSTRUCTION",
                            error=str(summary.get("error", "")),
                        ),
                    )
                    completed.add(identity)
                    continue
                if new.exists():
                    raise FileExistsError(f"strict continuation already exists: {new}")
                cases = strict_cases(
                    count, f"DEV-V12-PERF-CONT-{baseline}-C{count}-R{rep}"
                )
                c0 = cpu_clock_ns()
                t0 = time.monotonic_ns()
                summary = execute_once(
                    new,
                    runner,
                    PROFILE,
                    "OpenAI Agents SDK",
                    "DYNAMIC_SEQUENCE",
                    cases,
                    pir_record_count=64,
                )
                wall = time.monotonic_ns() - t0
                status, misses, rounds = classified(summary)
                sizes = summary.get("strict_size_projection") or {}
                sent = sum(sizes.get("request_final_bytes", []))
                received = sum(sizes.get("response_final_bytes", []))
                p_sent, p_received = pir_bytes(new / "pir")
                action_latency: float | str = ""
                try:
                    action_latency = canonical_boundary_latency_ms(new)
                except (AssertionError, FileNotFoundError, KeyError):
                    pass
                append_record(
                    journal,
                    enrich(
                        row(
                            baseline,
                            count,
                            rep,
                            wall,
                            cpu_clock_ns() - c0,
                            sent,
                            received,
                            rss_bytes(),
                            p_sent,
                            p_received,
                            action_latency_ms=action_latency,
                            latency_boundary="CANONICAL_FRAMEWORK_RESULT",
                        ),
                        status=status,
                        functional=bool(summary.get("passed")),
                        schedule_misses=misses,
                        rounds_observed=rounds,
                        source_evidence="ONE_SHOT_STRICT_CONTINUATION_NOT_PREVIOUSLY_EXECUTED",
                        error=str(summary.get("error", "")),
                    ),
                )
                completed.add(identity)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--go-bench", type=Path, required=True)
    parser.add_argument("--resume-partial", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.resume_partial:
        raise FileExistsError("V12 performance recovery output is append-only and one-shot")
    if not args.output.exists():
        args.output.mkdir(parents=True)
    journal = args.output / "performance_attempts.jsonl"
    existing_rows = (
        [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        if journal.exists()
        else []
    )
    completed = {
        (item["baseline"], int(item["real_operations"]), int(item["repetition"]))
        for item in existing_rows
    }
    if len(completed) != len(existing_rows):
        raise RuntimeError("partial performance journal contains duplicate identities")
    rerun_non_strict(args.output, args.go_bench, journal, completed)
    reconstruct_or_continue_strict(
        args.failed_root, args.output, args.runner, journal, completed
    )

    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    identities = [
        (item["baseline"], int(item["real_operations"]), int(item["repetition"]))
        for item in rows
    ]
    if len(rows) != 900 or len(set(identities)) != 900:
        raise AssertionError("performance recovery did not produce exactly 900 unique attempts")
    with (args.output / "performance_raw.csv").open(
        "x", encoding="utf-8", newline=""
    ) as stream:
        fields = list(rows[0])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    strict = [item for item in rows if item["baseline"] in STRICT_BASELINES]
    strict_failures = [item for item in strict if not item["functional"]]
    strict_successes = [item for item in strict if item["functional"]]
    bytes_verified = all(
        int(item["bytes_sent"]) + int(item["bytes_received"]) == 668_924
        for item in strict_successes
    )
    result = {
        "schema": "AgentTool.V12PerformanceRecovery/1",
        "status": "PASS" if not strict_failures else "COMPLETE_WITH_RETAINED_FAILURES",
        "rows": 900,
        "cells": 30,
        "repetitions_per_cell": 30,
        "strict_sessions": 300,
        "strict_successful_sessions": len(strict_successes),
        "strict_failures": len(strict_failures),
        "strict_failure_identities": [
            {
                "baseline": item["baseline"],
                "real_operations": item["real_operations"],
                "repetition": item["repetition"],
                "status_class": item["status_class"],
                "schedule_misses": item["schedule_misses"],
                "rounds_observed": item["rounds_observed"],
            }
            for item in strict_failures
        ],
        "strict_rounds": 356,
        "strict_scheduled_lifetime_ms": 3560,
        "strict_action_transport_bytes": 668_924,
        "strict_successful_relay_bytes_verified": bytes_verified,
        "strict_all_attempts_relay_bytes_verified": not strict_failures and bytes_verified,
        "failed_campaign_preserved": True,
        "strict_failed_unit_retried": False,
        "selected_v12_cases_executed": 0,
    }
    (args.output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
