from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

from scripts.run_v11_3_profile_closure import execute_once, strict_cases
from scripts.run_v12_performance import canonical_boundary_latency_ms, cpu_clock_ns, pir_bytes, row, rss_bytes
from v11_4.profile import selected_profile


PROFILE = selected_profile(10, 3000)
BASELINES = ("B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL", "B5_FULL_STRICT")
COUNTS = (1, 5, 10, 25, 50)
REPETITIONS = 30


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    runner = args.runner.resolve()
    identities = []
    for baseline in BASELINES:
        for count in COUNTS:
            for repetition in range(REPETITIONS):
                label = f"DEV-V12_1-AFFECTED-PERF-{baseline}-C{count}-R{repetition:02d}"
                cases = strict_cases(count, label)
                identities.append({
                    "baseline": baseline,
                    "count": count,
                    "repetition": repetition,
                    "case_ids": [case.case_id for case in cases],
                    "operation_ids": [case.operation_id for case in cases],
                })
    write_json_exclusive(root / "frozen_dev_identities.json", {
        "schema": "AgentTool.V12_1.AffectedPerformanceIdentityFreeze/1",
        "profile": PROFILE.public_schema(),
        "runner": str(runner),
        "runner_sha256": sha256(runner),
        "identities": identities,
        "selected_v12_cases_executed": 0,
    })
    rows = []
    for identity in identities:
        baseline = identity["baseline"]
        count = identity["count"]
        repetition = identity["repetition"]
        label = f"DEV-V12_1-AFFECTED-PERF-{baseline}-C{count}-R{repetition:02d}"
        cases = strict_cases(count, label)
        session_root = root / "strict_raw" / baseline / f"c{count}" / f"{repetition:02d}"
        cpu_start = cpu_clock_ns()
        wall_start = time.monotonic_ns()
        value = execute_once(
            session_root,
            runner,
            PROFILE,
            "OpenAI Agents SDK",
            "DYNAMIC_SEQUENCE",
            cases,
            pir_record_count=64,
        )
        wall_ns = time.monotonic_ns() - wall_start
        if not value.get("passed"):
            raise RuntimeError(f"affected performance session failed {baseline}/{count}/{repetition}: {value.get('error')}")
        sizes = value["strict_size_projection"]
        sent = sum(sizes["request_final_bytes"])
        received = sum(sizes["response_final_bytes"])
        if sent + received != 668_924:
            raise AssertionError("strict Relay-observed byte total mismatch")
        pir_sent, pir_received = pir_bytes(session_root / "pir")
        rows.append(row(
            baseline,
            count,
            repetition,
            wall_ns,
            cpu_clock_ns() - cpu_start,
            sent,
            received,
            rss_bytes(),
            pir_sent,
            pir_received,
            canonical_boundary_latency_ms(session_root),
            "CANONICAL_FRAMEWORK_RESULT",
        ))
        print(json.dumps({"baseline": baseline, "count": count, "repetition": repetition, "status": "PASS"}), flush=True)
    with (root / "performance_raw.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json_exclusive(root / "result.json", {
        "schema": "AgentTool.V12_1.AffectedPerformance/1",
        "status": "PASS",
        "rows": len(rows),
        "B4_functional": 150,
        "B5_functional": 150,
        "selected_v12_cases_executed": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
