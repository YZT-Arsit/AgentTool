from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def identities() -> dict[str, Any]:
    session_ids = [f"DEV-SCHED-CURRENT-NOOP-{index:04d}" for index in range(500)]
    return {
        "schema": "AgentTool.V12SchedulerCurrentNoopIdentities/1",
        "development_only": True,
        "session_count": 500,
        "rounds_per_session": 356,
        "round_period_ms": 10,
        "provider_work": 0,
        "session_ids": session_ids,
        "identity_sha256": hashlib.sha256(
            json.dumps(session_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "selected_v12_cases_executed": 0,
    }


def plan(session_id: str, state_directory: Path) -> dict[str, Any]:
    return {
        "profile_id": "V11_4-STRICT-ONLINE-H50-H3000-P10",
        "state_directory": str(state_directory),
        "rounds": 356,
        "admission_rounds": 300,
        "maximum_real_operations": 50,
        "round_period_ms": 10,
        "provider_completion_bound_ms": 50,
        "request_bhttp_bytes": 1024,
        "response_bhttp_bytes": 768,
        "request_final_bytes": 1079,
        "response_final_bytes": 800,
        "scheduler_tolerance_ms": 3,
        "preparation_lead_ms": 1,
        "routes": [],
        "actions": [],
        "development_session_id": session_id,
    }


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != identities():
        raise AssertionError("scheduler identity manifest changed")
    write_json_exclusive(
        root / "execution_started.json",
        {
            "identity_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "selected_v12_cases_executed": 0,
        },
    )
    rows = []
    for index, session_id in enumerate(manifest["session_ids"]):
        output = root / "raw" / f"{index:04d}-{session_id}"
        output.mkdir(parents=True)
        plan_path = output / "plan.json"
        result_path = output / "result.json"
        write_json_exclusive(plan_path, plan(session_id, output / "state"))
        completed = subprocess.run(
            [
                str(runner),
                "--online",
                "--plan",
                str(plan_path),
                "--output",
                str(result_path),
            ],
            input="",
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        (output / "stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
        (output / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if not result_path.is_file():
            failure = {
                "session_index": index,
                "session_id": session_id,
                "failure_class": "RUNNER_RESULT_ABSENT",
                "return_code": completed.returncode,
                "stderr": completed.stderr,
                "retry_performed": False,
            }
            write_json_exclusive(root / "first_failure.json", failure)
            raise RuntimeError(str(failure))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        launches = result.get("slot_launches", [])
        slips = [int(value.get("launch_slip_ns", 0)) for value in launches]
        row = {
            "session_index": index,
            "session_id": session_id,
            "session_status": result.get("session_status"),
            "rounds_emitted": len(result.get("public_relay_events", [])),
            "schedule_misses": int(result.get("schedule_misses", 0)),
            "provider_invocations": int(result.get("provider_invocations", 0)),
            "max_launch_slip_ns": max(slips, default=0),
            "max_wake_lateness_ns": max(
                (int(value.get("wake_lateness_ns", 0)) for value in launches), default=0
            ),
        }
        rows.append(row)
        if (
            completed.returncode != 0
            or row["session_status"] != "COMPLETE"
            or row["rounds_emitted"] != 356
            or row["schedule_misses"] != 0
            or row["provider_invocations"] != 0
        ):
            write_json_exclusive(
                root / "first_failure.json",
                {
                    **row,
                    "return_code": completed.returncode,
                    "scheduler_incidents": result.get("scheduler_incidents", []),
                    "missed_slots": [
                        value for value in launches if value.get("schedule_miss")
                    ],
                    "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise RuntimeError(f"current scheduler failed at {session_id}")
        if (index + 1) % 10 == 0:
            print(f"V12_SCHEDULER_NOOP {index + 1}/500", flush=True)
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12SchedulerCurrentNoopResult/1",
            "sessions_passed": len(rows),
            "sessions_total": 500,
            "scheduled_slots": 178000,
            "provider_invocations": 0,
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
            raise FileExistsError("scheduler NOOP output root exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identities())
    else:
        execute(args.output, args.runner)


if __name__ == "__main__":
    main()
