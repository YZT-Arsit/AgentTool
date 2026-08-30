from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.run_v11_3_profile_closure import execute_once, strict_cases
from v11_4.profile import selected_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILE = selected_profile(10, 3000)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def exact_gate(value: dict[str, Any], expected: list[str]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    trace = value.get("trace_gate") or {}
    diagnostic = value.get("diagnostic_operation_ids") or {}
    size_projection = value.get("strict_size_projection") or {}
    for field in (
        "action_intent_submitted",
        "dynamic_pir_descriptor_recovered",
        "accepted",
        "admitted",
        "provider_invoked",
        "result_committed",
        "result_available",
        "framework_delivered",
    ):
        if diagnostic.get(field) != expected:
            failures.append(f"{field}_ids")
    for field in ("pending", "resolved_not_admitted", "unresolved", "framework_waiters"):
        if diagnostic.get(field, []) != []:
            failures.append(field)
    checks = {
        "passed": value.get("passed") is True,
        "rounds": trace.get("rounds") == 356,
        "schedule_misses": trace.get("schedule_misses") == 0,
        "dummy_heavy_ops": trace.get("dummy_heavy_ops") == 0,
        "profile_overflow": trace.get("profile_overflow") == 0,
        "silent_committed_result_loss": trace.get("silent_committed_result_loss") == 0,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "size_request": set(size_projection.get("request_final_bytes", [])) == {1079},
        "size_response": set(size_projection.get("response_final_bytes", [])) == {800},
    }
    failures.extend(name for name, passed in checks.items() if not passed)
    return not failures, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--counts", type=int, nargs="+", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--decisive", action="store_true")
    args = parser.parse_args()
    counts = tuple(args.counts)
    if args.decisive and (counts != (25, 50) or args.repetitions != 100):
        raise ValueError("decisive V12.1 B5 denominator must be 100 each at counts 25 and 50")
    if not args.decisive and (args.repetitions > 20 or any(count not in {25, 50} for count in counts)):
        raise ValueError("development pilot is bounded to at most 20 repetitions")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runner = args.runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(runner)
    identities = []
    for count in counts:
        for repetition in range(args.repetitions):
            cases = strict_cases(count, f"DEV-V12_1-{args.label}-C{count}-R{repetition:03d}")
            identities.append(
                {
                    "count": count,
                    "repetition": repetition,
                    "case_ids": [case.case_id for case in cases],
                    "operation_ids": [case.operation_id for case in cases],
                }
            )
    write_json_exclusive(
        output / "frozen_dev_identities.json",
        {
            "schema": "AgentTool.V12_1.B5ReliabilityIdentityFreeze/1",
            "label": args.label,
            "decisive": args.decisive,
            "counts": counts,
            "repetitions_per_count": args.repetitions,
            "profile": PROFILE.__dict__,
            "runner": str(runner),
            "runner_sha256": sha256(runner),
            "identities": identities,
            "selected_v12_cases": False,
        },
    )
    ledger = output / "attempts.jsonl"
    passed = 0
    total = len(identities)
    for identity in identities:
        count = identity["count"]
        repetition = identity["repetition"]
        cases = strict_cases(count, f"DEV-V12_1-{args.label}-C{count}-R{repetition:03d}")
        session_root = output / f"c{count}" / f"r{repetition:03d}"
        try:
            value = execute_once(
                session_root,
                runner,
                PROFILE,
                "OpenAI Agents SDK",
                "DYNAMIC_SEQUENCE",
                cases,
                pir_record_count=64,
            )
            error = ""
        except Exception as exc:
            value = {}
            error = f"{type(exc).__name__}: {exc}"
        exact, failures = exact_gate(value, identity["operation_ids"])
        if exact and not error:
            passed += 1
        record = {
            "count": count,
            "repetition": repetition,
            "passed": exact and not error,
            "failures": failures,
            "error": error or value.get("error", ""),
            "session_status": value.get("trace_gate", {}).get("session_status", "NO_TRACE"),
            "rounds": value.get("trace_gate", {}).get("rounds", 0),
            "schedule_misses": value.get("trace_gate", {}).get("schedule_misses", -1),
            "session_root": session_root.relative_to(output).as_posix(),
        }
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        print(json.dumps(record, sort_keys=True), flush=True)
    summary = {
        "schema": "AgentTool.V12_1.B5ReliabilitySummary/1",
        "label": args.label,
        "decisive": args.decisive,
        "passed": passed,
        "attempted": total,
        "failed": total - passed,
        "selected_v12_cases_executed": 0,
    }
    write_json_exclusive(output / "summary.json", summary)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
