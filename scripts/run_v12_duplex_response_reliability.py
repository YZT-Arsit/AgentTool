from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.profile import duplex_response_closure_p10_profile


FREEZE = ROOT / "V12_DUPLEX_RESPONSE_STARTUP_QUALIFICATION_FREEZE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def exact_slots(rows: list[dict[str, object]], rounds: int) -> bool:
    return len(rows) == rounds and {int(row["round"]) for row in rows} == set(
        range(1, rounds + 1)
    )


def run_one(
    runner: Path, output: Path, identity: str, *, profile=None
) -> dict[str, object]:
    if profile is None:
        profile = duplex_response_closure_p10_profile()
    session = output / identity
    session.mkdir(parents=True, exist_ok=False)
    plan = profile.go_plan_fields()
    plan.update(
        {
            "state_directory": str(session / "gateway_state"),
            "routes": [
                {
                    "route_handle": "synthetic-unused-route",
                    "action_kind": "REAL_TOOL",
                    "effect_semantics": "READ_ONLY",
                    "endpoint": "http://127.0.0.1:9/unused",
                    "policy_id": "synthetic-public-path-only",
                }
            ],
            "actions": [],
            "scheduler_tolerance_ms": 3,
            "preparation_lead_ms": 1,
        }
    )
    plan_path = session / "trusted_online_startup_plan.json"
    result_path = session / "go_online_result.json"
    write_json(plan_path, plan)
    started = time.time()
    completed = subprocess.run(
        [
            str(runner),
            "--online",
            "--plan",
            str(plan_path),
            "--output",
            str(result_path),
        ],
        cwd=ROOT,
        input="",
        text=True,
        capture_output=True,
        timeout=75,
        check=False,
    )
    (session / "runner_stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
    (session / "runner_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if not result_path.exists():
        raise RuntimeError(f"{identity}: runner produced no result (rc={completed.returncode})")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    relay = list(result.get("public_relay_events", []))
    releases = list(result.get("gateway_response_releases", []))
    checks = {
        "runner_exit_zero": completed.returncode == 0,
        "session_complete": result.get("session_status") == "COMPLETE",
        "public_transcript_complete": result.get("public_transcript_complete") is True,
        "exact_R_relay_events": len(relay) == profile.total_rounds,
        "exact_unique_slot_set": exact_slots(relay, profile.total_rounds),
        "release_opportunities_exact_R": int(
            result.get("response_release_opportunities", -1)
        )
        == profile.total_rounds,
        "release_attempts_exact_R": int(result.get("response_release_attempts", -1))
        == profile.total_rounds,
        "successful_writes_exact_R": int(
            result.get("successful_response_writes", -1)
        )
        == profile.total_rounds,
        "relay_received_exact_R": int(
            result.get("relay_application_received_cells", -1)
        )
        == profile.total_rounds,
        "emitted_cells_are_successful_writes": int(result.get("emitted_cells", -1))
        == profile.total_rounds,
        "gateway_release_records_exact_R": len(releases) == profile.total_rounds,
        "every_release_write_completed": all(
            row.get("release_attempted") is True
            and row.get("response_write_completed") is True
            for row in releases
        ),
        "no_transport_diagnostic": result.get("transport_diagnostics", []) == [],
    }
    record = {
        "identity": identity,
        "elapsed_seconds": time.time() - started,
        "checks": checks,
        "pass": all(checks.values()),
        "result_sha256": sha256(result_path),
        "deadline_miss_count": sum(bool(row.get("deadline_miss")) for row in releases),
        "maximum_release_slip_ns": max(
            (int(row.get("release_slip_ns", 0)) for row in releases), default=0
        ),
    }
    write_json(session / "reliability_record.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=FREEZE)
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    identities = list(freeze["synthetic_reliability_identities"])
    if len(identities) != 200 or len(set(identities)) != 200:
        raise RuntimeError("reliability identity freeze is malformed")
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = args.output / "execution_ledger.jsonl"
    records: list[dict[str, object]] = []
    for ordinal, identity in enumerate(identities, start=1):
        record = run_one(args.runner, args.output, identity)
        record["ordinal"] = ordinal
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        records.append(record)
        if not bool(record["pass"]):
            break
    passed = sum(bool(record["pass"]) for record in records)
    summary = {
        "schema": "AgentTool.V12DuplexResponseStartupReliability/1",
        "profile_id": duplex_response_closure_p10_profile().profile_id,
        "planned_sessions": 200,
        "executed_sessions": len(records),
        "passed_sessions": passed,
        "failed_sessions": len(records) - passed,
        "retries": 0,
        "protected_workload_classes": 0,
        "classifier_runs": 0,
        "auc_calculations": 0,
        "status": "PASS" if passed == 200 else "FAIL",
        "records": records,
    }
    write_json(args.output / "SYNTHETIC_RELIABILITY_SUMMARY.json", summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
