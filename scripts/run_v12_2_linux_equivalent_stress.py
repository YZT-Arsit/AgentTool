from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from v11_full_scope.canonical import canonical_external_outcome, canonical_multi_action
from v11_full_scope.fixtures import agent_case, tool_case
from v11_full_scope.models import AgentServiceSubtype


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def validate_trace(trace: dict[str, object], expected_ids: list[str], expected_rounds: int) -> list[str]:
    failures: list[str] = []
    actual_ids = [str(item.get("operation_id")) for item in trace.get("results", [])]
    checks = {
        "session_complete": trace.get("session_status") == "COMPLETE",
        "rounds": len(trace.get("public_relay_events", [])) == expected_rounds,
        "schedule_miss": int(trace.get("schedule_misses", -1)) == 0,
        "profile_overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "silent_committed_result_loss": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "provider_invocations": int(trace.get("provider_invocations", -1)) == len(expected_ids),
        "result_ids": actual_ids == expected_ids,
        "pending": list(trace.get("pending_operation_ids", [])) == [],
        "request_sizes": {int(row.get("request_length", -1)) for row in trace.get("public_relay_events", [])} == {1079},
        "response_sizes": {int(row.get("response_length", -1)) for row in trace.get("public_relay_events", [])} == {800},
    }
    failures.extend(name for name, passed in checks.items() if not passed)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if args.repetitions != 100:
        raise ValueError("V12.2 equivalent stress denominator is frozen at 100 per family")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runner = args.runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(runner)

    identities: list[dict[str, object]] = []
    for repetition in range(args.repetitions):
        tool_cases = [
            replace(
                tool_case(f"DEV-V12_2-{args.label}-TOOL10-R{repetition:03d}-I{index:02d}", "FRAMEWORK_NEUTRAL"),
                operation_id=f"v122tool10r{repetition:03d}i{index:02d}",
            )
            for index in range(10)
        ]
        identities.append(
            {
                "family": "TOOL_MULTI_ACTION_10",
                "repetition": repetition,
                "case_ids": [case.case_id for case in tool_cases],
                "operation_ids": [case.operation_id for case in tool_cases],
            }
        )
        subtype = agent_case(
            f"DEV-V12_2-{args.label}-AGENT-SUBTYPE-R{repetition:03d}",
            "FRAMEWORK_NEUTRAL",
            AgentServiceSubtype.AGENT_AS_TOOL,
        )
        subtype = replace(
            subtype,
            operation_id=f"v122agentsubtyper{repetition:03d}",
            continuation={"context": "x" * 128},
            arguments={"task": "y" * 128},
        )
        identities.append(
            {
                "family": "AGENT_SERVICE_PRIVATE_SUBTYPE",
                "repetition": repetition,
                "case_ids": [subtype.case_id],
                "operation_ids": [subtype.operation_id],
            }
        )

    write_json_exclusive(
        output / "frozen_dev_identities.json",
        {
            "schema": "AgentTool.V12_2.LinuxEquivalentStressIdentities/1",
            "label": args.label,
            "repetitions_per_family": args.repetitions,
            "runner": str(runner),
            "runner_sha256": sha256(runner),
            "identities": identities,
            "selected_v12_cases": False,
        },
    )

    rows: list[dict[str, object]] = []
    for identity in identities:
        family = str(identity["family"])
        repetition = int(identity["repetition"])
        operation_ids = list(identity["operation_ids"])
        root = output / family.lower() / f"r{repetition:03d}"
        error = ""
        failures: list[str] = []
        try:
            if family == "TOOL_MULTI_ACTION_10":
                cases = [
                    replace(
                        tool_case(f"DEV-V12_2-{args.label}-TOOL10-R{repetition:03d}-I{index:02d}", "FRAMEWORK_NEUTRAL"),
                        operation_id=f"v122tool10r{repetition:03d}i{index:02d}",
                    )
                    for index in range(10)
                ]
                value = canonical_multi_action(cases, root, runner_binary=runner)
                trace_path = root / "canonical_session" / "go_canonical_result.json"
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
                failures.extend(validate_trace(trace, operation_ids, 111))
                if not value.get("functional"):
                    failures.append("functional")
                if int(value.get("delivered", -1)) != 10:
                    failures.append("delivered")
            else:
                case = agent_case(
                    f"DEV-V12_2-{args.label}-AGENT-SUBTYPE-R{repetition:03d}",
                    "FRAMEWORK_NEUTRAL",
                    AgentServiceSubtype.AGENT_AS_TOOL,
                )
                case = replace(
                    case,
                    operation_id=f"v122agentsubtyper{repetition:03d}",
                    continuation={"context": "x" * 128},
                    arguments={"task": "y" * 128},
                )
                outcome = canonical_external_outcome(case, root, runner_binary=runner)
                trace = outcome.evidence["raw_trace"]
                failures.extend(validate_trace(trace, operation_ids, 111))
                if int(outcome.evidence.get("relay_rounds", -1)) != 111:
                    failures.append("relay_rounds")
                if int(outcome.evidence.get("dummy_provider_operations", -1)) != 0:
                    failures.append("dummy_provider_operations")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        passed = not failures and not error
        row = {
            "family": family,
            "repetition": repetition,
            "passed": passed,
            "failure_fields": ";".join(failures),
            "error": error,
            "output_root": root.relative_to(output).as_posix(),
        }
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)

    with (output / "results.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema": "AgentTool.V12_2.LinuxEquivalentStressSummary/1",
        "families": {
            family: {
                "passed": sum(row["passed"] is True and row["family"] == family for row in rows),
                "attempted": sum(row["family"] == family for row in rows),
            }
            for family in ("TOOL_MULTI_ACTION_10", "AGENT_SERVICE_PRIVATE_SUBTYPE")
        },
        "selected_v12_cases_executed": 0,
    }
    write_json_exclusive(output / "summary.json", summary)
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
