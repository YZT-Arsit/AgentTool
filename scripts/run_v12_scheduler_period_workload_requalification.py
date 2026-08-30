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

from v11_4.profile import selected_profile
from v11_full_scope.fixtures import tool_case
from v11_online.frameworks import run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession


FRAMEWORKS = {
    "OA": "OpenAI Agents SDK",
    "MS": "Microsoft Agent Framework",
}
PERIOD_MS = 25
HORIZON_MS = 3000
PROFILE = selected_profile(PERIOD_MS, HORIZON_MS)


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def cases_for(code: str, depth: int, repetition: int):
    cases = []
    for index in range(depth):
        case = tool_case(
            f"DEV-SCHED-P25-WORK-{code}-D{depth}-{repetition:03d}-{index:02d}",
            FRAMEWORKS[code],
            effect_semantics="READ_ONLY",
        )
        cases.append(
            replace(
                case,
                capability="tool.read",
                arguments={
                    "city": f"scheduler-p25-{code.lower()}-d{depth}-{repetition:03d}-{index:02d}"
                },
            )
        )
    return tuple(cases)


def identities() -> dict[str, Any]:
    workflows = []
    for code in ("OA", "MS"):
        for repetition in range(100):
            cases = cases_for(code, 10, repetition)
            workflows.append(
                {
                    "workflow_id": f"DEV-SCHED-P25-{code}-REPEAT10-{repetition:03d}",
                    "framework": FRAMEWORKS[code],
                    "depth": 10,
                    "operation_ids": [case.operation_id for case in cases],
                }
            )
    for code in ("OA", "MS"):
        for repetition in range(20):
            cases = cases_for(code, 30, repetition)
            workflows.append(
                {
                    "workflow_id": f"DEV-SCHED-P25-{code}-REPEAT30-{repetition:03d}",
                    "framework": FRAMEWORKS[code],
                    "depth": 30,
                    "operation_ids": [case.operation_id for case in cases],
                }
            )
    payload = {
        "schema": "AgentTool.V12SchedulerPeriodWorkloadRequalificationIdentities/1",
        "development_only": True,
        "candidate_period_ms": PERIOD_MS,
        "profile": PROFILE.public_schema(),
        "workflow_count": len(workflows),
        "openai_repeat10": 100,
        "microsoft_repeat10": 100,
        "openai_repeat30": 20,
        "microsoft_repeat30": 20,
        "workflows": workflows,
        "retry_policy": "NO_RETRY",
        "selected_v12_cases_executed": 0,
    }
    payload["workflow_aggregate_sha256"] = hashlib.sha256(
        json.dumps(workflows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def reconstruct(item: dict[str, Any]):
    code = "OA" if item["framework"] == FRAMEWORKS["OA"] else "MS"
    repetition = int(item["workflow_id"].rsplit("-", 1)[1])
    cases = cases_for(code, int(item["depth"]), repetition)
    if [case.operation_id for case in cases] != item["operation_ids"]:
        raise AssertionError("frozen p25 workload identity did not reconstruct")
    return cases


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != identities():
        raise AssertionError("p25 workload identity manifest changed")
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
        cases = reconstruct(item)
        output = root / "raw" / f"{index:03d}-{item['workflow_id']}"
        try:
            with CanonicalOnlineSession(
                output,
                list(cases),
                runner_binary=runner,
                public_profile=PROFILE,
            ) as session:
                semantic = run_online_framework_workflow(
                    item["framework"], "DYNAMIC_SEQUENCE", list(cases), session.implementation()
                )
            trace = session.trace
            if trace is None:
                raise AssertionError("canonical session trace absent")
            causal = session.causal_proof()
        except BaseException as error:
            write_json_exclusive(
                root / "first_failure.json",
                {
                    "schema": "AgentTool.V12SchedulerP25WorkloadFirstFailure/1",
                    "workflow_index": index,
                    "workflow": item,
                    "failure_class": "EXECUTION_EXCEPTION",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise
        expected = list(item["operation_ids"])
        provider = trace.get("provider_diagnostics", [])
        provider_ids = [str(value.get("operation_id")) for value in provider]
        result_ids = [str(value.get("operation_id")) for value in trace.get("results", [])]
        accepted = [str(value) for value in trace.get("accepted_operation_ids", [])]
        row = {
            "workflow_id": item["workflow_id"],
            "framework": item["framework"],
            "depth": item["depth"],
            "session_status": trace.get("session_status"),
            "rounds_emitted": len(trace.get("public_relay_events", [])),
            "schedule_misses": int(trace.get("schedule_misses", 0)),
            "accepted_ids_exact": sorted(accepted) == sorted(expected),
            "provider_ids_exact": sorted(provider_ids) == sorted(expected),
            "result_ids_exact": sorted(result_ids) == sorted(expected),
            "provider_ok": sum(value.get("class") == "PROVIDER_OK" for value in provider),
            "causal_proof": bool(causal.get("passed")),
            "profile_overflow": int(trace.get("profile_overflow_events", 0)),
            "silent_committed_result_losses": int(trace.get("silent_committed_result_losses", 0)),
            "dummy_heavy_ops": int(trace.get("dummy_provider_operations", 0)),
            "semantic_projection_actions": len(semantic["projection"]["trajectory"]),
        }
        rows.append(row)
        passed = (
            row["session_status"] == "COMPLETE"
            and row["rounds_emitted"] == PROFILE.total_rounds
            and row["schedule_misses"] == 0
            and row["accepted_ids_exact"]
            and row["provider_ids_exact"]
            and row["result_ids_exact"]
            and row["provider_ok"] == item["depth"]
            and row["causal_proof"]
            and row["profile_overflow"] == 0
            and row["silent_committed_result_losses"] == 0
            and row["dummy_heavy_ops"] == 0
            and row["semantic_projection_actions"] == item["depth"]
        )
        if not passed:
            write_json_exclusive(
                root / "first_failure.json",
                {
                    "schema": "AgentTool.V12SchedulerP25WorkloadFirstFailure/1",
                    "workflow_index": index,
                    "workflow": item,
                    "summary": row,
                    "scheduler_incidents": trace.get("scheduler_incidents", []),
                    "missed_slots": [
                        value for value in trace.get("slot_launches", []) if value.get("schedule_miss")
                    ],
                    "provider_diagnostics": provider,
                    "go_result_sha256": hashlib.sha256(
                        (output / "go_online_result.json").read_bytes()
                    ).hexdigest(),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise RuntimeError(f"p25 workload failed at {item['workflow_id']}")
        if (index + 1) % 10 == 0:
            print(f"V12_PERIOD_25_WORKLOAD {index + 1}/240", flush=True)
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12SchedulerP25WorkloadResult/1",
            "profile": PROFILE.public_schema(),
            "workflows_passed": len(rows),
            "workflows_total": 240,
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
            raise FileExistsError("p25 workload requalification root exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identities())
    else:
        execute(args.output, args.runner)


if __name__ == "__main__":
    main()
