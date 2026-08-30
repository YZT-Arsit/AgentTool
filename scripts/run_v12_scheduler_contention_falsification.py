from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.fixtures import tool_case
from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    TrajectorySpec,
    run_canonical_online_trajectory_case,
)


FRAMEWORKS = {
    "OA": "OpenAI Agents SDK",
    "MS": "Microsoft Agent Framework",
}
PERMIT = ExecutionPermit("V11A_DEVELOPMENT_REGRESSION", True)


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def make_cases(code: str, repetition: int):
    cases = []
    for index in range(10):
        case = tool_case(
            f"DEV-SCHED-CONTENTION2-{code}-{repetition:03d}-{index:02d}",
            FRAMEWORKS[code],
            effect_semantics="READ_ONLY",
        )
        cases.append(
            replace(
                case,
                capability="tool.read",
                arguments={"city": f"scheduler-contention-{code.lower()}-{repetition:03d}-{index:02d}"},
            )
        )
    return tuple(cases)


def identity_manifest() -> dict[str, Any]:
    workflows = []
    for code, framework in FRAMEWORKS.items():
        for repetition in range(100):
            cases = make_cases(code, repetition)
            workflows.append(
                {
                    "workflow_id": f"DEV-SCHED-CONTENTION2-{code}-REPEAT10-{repetition:03d}",
                    "framework": framework,
                    "operation_ids": [case.operation_id for case in cases],
                    "depth": 10,
                }
            )
    payload = {
        "schema": "AgentTool.V12SchedulerContentionIdentities/1",
        "development_only": True,
        "workflows": workflows,
        "workflow_count": len(workflows),
        "openai_workflows": 100,
        "microsoft_workflows": 100,
        "prior_decisive_identity_executed": False,
        "selected_v12_cases_executed": 0,
    }
    payload["workflow_aggregate_sha256"] = hashlib.sha256(
        json.dumps(workflows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def cases_for(item: dict[str, Any]):
    code = "OA" if item["framework"] == FRAMEWORKS["OA"] else "MS"
    repetition = int(item["workflow_id"].rsplit("-", 1)[1])
    cases = make_cases(code, repetition)
    if [case.operation_id for case in cases] != item["operation_ids"]:
        raise AssertionError("frozen contention identity did not reconstruct")
    return cases


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != identity_manifest():
        raise AssertionError("scheduler contention identity manifest changed")
    write_json_exclusive(
        root / "execution_started.json",
        {
            "identity_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "selected_v12_cases_executed": 0,
        },
    )
    rows = []
    for index, item in enumerate(manifest["workflows"]):
        cases = cases_for(item)
        spec = TrajectorySpec(item["workflow_id"], item["framework"], "DYNAMIC_SEQUENCE", cases)
        output = root / "raw" / f"{index:03d}-{item['workflow_id']}"
        canonical = run_canonical_online_trajectory_case(
            spec, output, PERMIT, runner_binary=runner
        )
        trace = canonical["raw_trace"]
        diagnostics = trace.get("provider_diagnostics", [])
        launches = trace.get("slot_launches", [])
        expected_ids = list(item["operation_ids"])
        observed_ids = [str(value.get("operation_id")) for value in diagnostics]
        row = {
            "workflow_id": item["workflow_id"],
            "framework": item["framework"],
            "session_status": trace.get("session_status"),
            "rounds_emitted": len(trace.get("public_relay_events", [])),
            "schedule_misses": int(trace.get("schedule_misses", 0)),
            "provider_attempts": len(diagnostics),
            "provider_ok": sum(value.get("class") == "PROVIDER_OK" for value in diagnostics),
            "operation_ids_exact": sorted(observed_ids) == sorted(expected_ids),
            "max_launch_slip_ns": max(
                (int(value.get("launch_slip_ns", 0)) for value in launches), default=0
            ),
            "max_wake_lateness_ns": max(
                (int(value.get("wake_lateness_ns", 0)) for value in launches), default=0
            ),
        }
        rows.append(row)
        functional = (
            row["session_status"] == "COMPLETE"
            and row["rounds_emitted"] == 356
            and row["schedule_misses"] == 0
            and row["provider_attempts"] == 10
            and row["provider_ok"] == 10
            and row["operation_ids_exact"]
        )
        if not functional:
            write_json_exclusive(
                root / "first_failure.json",
                {
                    "schema": "AgentTool.V12SchedulerContentionFirstFailure/1",
                    "workflow_index": index,
                    "workflow": item,
                    "summary": row,
                    "scheduler_incidents": trace.get("scheduler_incidents", []),
                    "missed_slots": [
                        value for value in launches if value.get("schedule_miss")
                    ],
                    "provider_diagnostics": diagnostics,
                    "go_result_sha256": hashlib.sha256(
                        (output / "go_online_result.json").read_bytes()
                    ).hexdigest(),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise RuntimeError(f"scheduler contention failure at {item['workflow_id']}")
        if (index + 1) % 10 == 0:
            print(f"V12_SCHEDULER_CONTENTION {index + 1}/200", flush=True)
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12SchedulerContentionResult/1",
            "workflows_passed": len(rows),
            "workflows_total": 200,
            "rows": rows,
            "retry_performed": False,
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
            raise FileExistsError("scheduler contention output root exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identity_manifest())
    else:
        execute(args.output, args.runner)


if __name__ == "__main__":
    main()
