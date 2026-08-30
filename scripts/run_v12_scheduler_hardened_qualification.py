from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from run_v12_scheduler_noop_falsification import plan


SESSION_COUNT = 1000


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def identities() -> dict[str, Any]:
    session_ids = [f"DEV-SCHED-HARDENED-NOOP-{index:04d}" for index in range(SESSION_COUNT)]
    return {
        "schema": "AgentTool.V12SchedulerHardenedQualificationIdentities/1",
        "development_only": True,
        "session_count": SESSION_COUNT,
        "rounds_per_session": 356,
        "round_period_ms": 10,
        "provider_work": 0,
        "required_pacer_cpu": 207,
        "required_framework_process_cpu_set": "0-206",
        "session_ids": session_ids,
        "identity_sha256": hashlib.sha256(
            json.dumps(session_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "selected_v12_cases_executed": 0,
    }


def percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1)]


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != identities():
        raise AssertionError("hardened scheduler identity manifest changed")
    write_json_exclusive(
        root / "execution_started.json",
        {
            "identity_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "selected_v12_cases_executed": 0,
        },
    )
    rows = []
    launch_slips: list[int] = []
    wake_lateness: list[int] = []
    for index, session_id in enumerate(manifest["session_ids"]):
        output = root / "raw" / f"{index:04d}-{session_id}"
        output.mkdir(parents=True)
        plan_path = output / "plan.json"
        result_path = output / "result.json"
        write_json_exclusive(plan_path, plan(session_id, output / "state"))
        completed = subprocess.run(
            [str(runner), "--online", "--plan", str(plan_path), "--output", str(result_path)],
            input="",
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        (output / "stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
        (output / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if not result_path.is_file():
            write_json_exclusive(
                root / "first_failure.json",
                {
                    "session_index": index,
                    "session_id": session_id,
                    "failure_class": "RUNNER_RESULT_ABSENT",
                    "return_code": completed.returncode,
                    "stderr": completed.stderr,
                    "retry_performed": False,
                },
            )
            raise RuntimeError(f"runner result absent at {session_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        launches = result.get("slot_launches", [])
        slips = [int(value.get("launch_slip_ns", 0)) for value in launches]
        wakes = [int(value.get("wake_lateness_ns", 0)) for value in launches]
        launch_slips.extend(slips)
        wake_lateness.extend(wakes)
        config = result.get("scheduler_configuration", {})
        row = {
            "session_index": index,
            "session_id": session_id,
            "session_status": result.get("session_status"),
            "rounds_emitted": len(result.get("public_relay_events", [])),
            "schedule_misses": int(result.get("schedule_misses", 0)),
            "provider_invocations": int(result.get("provider_invocations", 0)),
            "max_launch_slip_ns": max(slips, default=0),
            "max_wake_lateness_ns": max(wakes, default=0),
            "pacer_cpu": config.get("pacer_cpu"),
            "isolation_verified": config.get("isolation_verified"),
            "implementation": config.get("implementation"),
        }
        rows.append(row)
        passed = (
            completed.returncode == 0
            and row["session_status"] == "COMPLETE"
            and row["rounds_emitted"] == 356
            and row["schedule_misses"] == 0
            and row["provider_invocations"] == 0
            and row["pacer_cpu"] == 207
            and row["isolation_verified"] is True
            and row["implementation"] == "LINUX_CLOCK_NANOSLEEP_TIMER_ABSTIME"
        )
        if not passed:
            write_json_exclusive(
                root / "first_failure.json",
                {
                    **row,
                    "return_code": completed.returncode,
                    "scheduler_configuration": config,
                    "scheduler_incidents": result.get("scheduler_incidents", []),
                    "missed_slots": [value for value in launches if value.get("schedule_miss")],
                    "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise RuntimeError(f"hardened scheduler failed at {session_id}")
        if (index + 1) % 10 == 0:
            print(f"V12_HARDENED_SCHEDULER {index + 1}/{SESSION_COUNT}", flush=True)
    distribution = {
        "p50_ns": percentile(launch_slips, 0.50),
        "p95_ns": percentile(launch_slips, 0.95),
        "p99_ns": percentile(launch_slips, 0.99),
        "p99_9_ns": percentile(launch_slips, 0.999),
        "max_launch_slip_ns": max(launch_slips),
        "max_wake_lateness_ns": max(wake_lateness),
    }
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12SchedulerHardenedQualificationResult/1",
            "sessions_passed": len(rows),
            "sessions_total": SESSION_COUNT,
            "scheduled_slots": len(launch_slips),
            "schedule_misses": 0,
            "provider_invocations": 0,
            "distribution": distribution,
            "rows": rows,
            "selected_v12_cases_executed": 0,
            "status": "PASS",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--freeze-identities", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.freeze_identities == args.execute:
        raise ValueError("choose exactly one mode")
    if args.freeze_identities:
        if args.output.exists():
            raise FileExistsError("hardened scheduler qualification root exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identities())
    else:
        execute(args.output, args.runner)


if __name__ == "__main__":
    main()
