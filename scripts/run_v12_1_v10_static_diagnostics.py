from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from v11_full_scope.canonical import canonical_multi_action
from v11_full_scope.fixtures import tool_case


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def cases_for(repetition: int):
    return [
        replace(
            tool_case(f"DEV-V12_1-V10-H50-R{repetition:03d}-{index:02d}", "FRAMEWORK_NEUTRAL"),
            operation_id=f"v121v10h50r{repetition:03d}o{index:02d}",
        )
        for index in range(50)
    ]


def classify(error: str, trace: dict[str, Any] | None) -> str:
    diagnostics = (trace or {}).get("transport_diagnostics", [])
    if diagnostics:
        classes = sorted({str(item.get("failure_class")) for item in diagnostics})
        return "+".join(classes)
    lowered = error.lower()
    status = str((trace or {}).get("session_status", ""))
    if status == "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT":
        return "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT"
    if status == "SESSION_TRANSPORT_FAILURE" and not diagnostics:
        return "TRANSPORT_FAILURE_WITHOUT_LEGACY_DETAIL"
    if "schedule" in lowered or (trace and trace.get("schedule_misses")):
        return "SCHEDULE_MISS"
    if "ohttp" in lowered:
        return "OHTTP_ENCAPSULATION_FAILURE"
    if "bhttp" in lowered:
        return "BHTTP_ENCODING_FAILURE"
    if "relay" in lowered:
        return "RELAY_FAILURE"
    if "provider" in lowered:
        return "PROVIDER_COMPLETION_ISSUE"
    if "response final size" in lowered or "observed_body_bytes" in lowered:
        return "RESPONSE_BODY_LENGTH_MISMATCH_LEGACY_ERROR"
    return "PASS" if not error and trace and trace.get("session_status") == "COMPLETE" else "OTHER_EXACT_CLASS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=100)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=100)
    args = parser.parse_args()
    if args.attempts != 100:
        raise ValueError("the frozen V12.1 static diagnostic denominator is 100")
    if not (0 <= args.start < args.stop and args.stop - args.start <= 100):
        raise ValueError("invalid frozen V12.1 diagnostic range")
    runner = args.runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(runner)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": "AgentTool.V12_1.V10H50StaticDiagnosticManifest/1",
        "attempts": args.stop - args.start,
        "execution_range": [args.start, args.stop],
        "runner": str(runner),
        "runner_sha256": sha256(runner),
        "identities": [
            {
                "repetition": repetition,
                "case_ids": [case.case_id for case in cases_for(repetition)],
                "operation_ids": [case.operation_id for case in cases_for(repetition)],
            }
            for repetition in range(args.start, args.stop)
        ],
        "selected_v12_cases": False,
    }
    write_json_exclusive(output / "frozen_dev_identities.json", manifest)
    ledger_path = output / "attempts.jsonl"
    passed = 0
    for repetition in range(args.start, args.stop):
        attempt_root = output / f"r{repetition:03d}"
        error = ""
        result = None
        started = time.monotonic_ns()
        try:
            result = canonical_multi_action(
                cases_for(repetition), attempt_root, runner_binary=runner
            )
        except Exception as exc:  # evidence retains exact development failure
            error = f"{type(exc).__name__}: {exc}"
        trace_path = attempt_root / "canonical_session" / "go_canonical_result.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.is_file() else None
        functional = bool(result and result.get("functional") and trace and trace.get("session_status") == "COMPLETE")
        if functional:
            passed += 1
        record = {
            "repetition": repetition,
            "functional": functional,
            "classification": classify(error, trace),
            "error": error,
            "session_status": None if trace is None else trace.get("session_status"),
            "schedule_misses": None if trace is None else trace.get("schedule_misses"),
            "transport_diagnostics": [] if trace is None else trace.get("transport_diagnostics", []),
            "elapsed_ms": (time.monotonic_ns() - started) / 1_000_000,
            "attempt_root": attempt_root.relative_to(output).as_posix(),
        }
        with ledger_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        print(json.dumps(record, sort_keys=True), flush=True)
    write_json_exclusive(
        output / "summary.json",
        {
            "schema": "AgentTool.V12_1.V10H50StaticDiagnosticSummary/1",
            "passed": passed,
            "attempted": args.stop - args.start,
            "failed": args.stop - args.start - passed,
            "selected_v12_cases_executed": 0,
        },
    )
    return 0 if passed == args.stop - args.start else 1


if __name__ == "__main__":
    raise SystemExit(main())
