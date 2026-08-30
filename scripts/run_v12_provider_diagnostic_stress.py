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


def make_cases(code: str, repetition: int, depth: int = 10):
    cases = []
    for index in range(depth):
        case = tool_case(
            f"DEV-PC-DIAG-{code}-{repetition:03d}-{index:02d}",
            FRAMEWORKS[code],
            effect_semantics="READ_ONLY",
        )
        cases.append(
            replace(
                case,
                capability="tool.read",
                arguments={"city": f"provider-diag-{code.lower()}-{repetition:03d}-{index:02d}"},
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
                    "workflow_id": f"DEV-PC-DIAG-{code}-REPEAT10-{repetition:03d}",
                    "framework": framework,
                    "depth": 10,
                    "operation_ids": [case.operation_id for case in cases],
                    "logical_action_names": [case.logical_action_name for case in cases],
                    "scenario": "READ_ONLY_SUCCESS",
                }
            )
    payload = {
        "schema": "AgentTool.V12ProviderDiagnosticStressIdentities/1",
        "development_only": True,
        "workflow_count": 200,
        "openai_workflows": 100,
        "microsoft_workflows": 100,
        "excluded_decisive_identity": "DEV-RC-OA-REPEAT10-007",
        "workflows": workflows,
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
        raise AssertionError("frozen provider diagnostic identity did not reconstruct")
    return cases


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != identity_manifest():
        raise AssertionError("provider diagnostic identity manifest changed")
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
        diagnostics = canonical["raw_trace"].get("provider_diagnostics", [])
        classes = [str(value.get("class")) for value in diagnostics]
        operation_ids = [str(value.get("operation_id")) for value in diagnostics]
        expected = list(item["operation_ids"])
        row = {
            "workflow_id": item["workflow_id"],
            "framework": item["framework"],
            "provider_attempts": len(diagnostics),
            "provider_classes": classes,
            "operation_ids_exact": sorted(operation_ids) == sorted(expected),
            "session_status": canonical["raw_trace"].get("session_status"),
            "schedule_misses": canonical["raw_trace"].get("schedule_misses"),
            "profile_overflow": canonical["raw_trace"].get("profile_overflow_events"),
            "silent_committed_result_losses": canonical["raw_trace"].get(
                "silent_committed_result_losses"
            ),
        }
        rows.append(row)
        if (
            len(diagnostics) != 10
            or any(value != "PROVIDER_OK" for value in classes)
            or not row["operation_ids_exact"]
        ):
            first = next(
                (value for value in diagnostics if value.get("class") != "PROVIDER_OK"),
                None,
            )
            provider_evidence = json.loads(
                (output / "private_provider_evidence.json").read_text(encoding="utf-8")
            )
            write_json_exclusive(
                root / "first_failure.json",
                {
                    "schema": "AgentTool.V12ProviderDiagnosticFirstFailure/1",
                    "workflow_index": index,
                    "workflow": item,
                    "workflow_summary": row,
                    "first_non_ok_provider_diagnostic": first,
                    "private_provider_evidence": provider_evidence,
                    "raw_trace_sha256": hashlib.sha256(
                        (output / "go_online_result.json").read_bytes()
                    ).hexdigest(),
                    "retry_performed": False,
                    "selected_v12_cases_executed": 0,
                },
            )
            raise RuntimeError(
                f"provider diagnostic campaign stopped at {item['workflow_id']}: {first}"
            )
        if (index + 1) % 10 == 0:
            print(f"V12_PROVIDER_DIAGNOSTIC {index + 1}/200", flush=True)
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12ProviderDiagnosticStressResult/1",
            "workflows_passed": len(rows),
            "provider_attempts": sum(row["provider_attempts"] for row in rows),
            "all_provider_classes": "PROVIDER_OK",
            "workflow_results": rows,
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
        raise ValueError("choose exactly one of --freeze-identities or --execute")
    if args.freeze_identities:
        if args.output.exists():
            raise FileExistsError("provider diagnostic output root already exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identity_manifest())
        return
    execute(args.output, args.runner)


if __name__ == "__main__":
    main()
