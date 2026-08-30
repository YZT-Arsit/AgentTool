from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.fixtures import tool_case
from v11_online.frameworks import PRIVATE_ROUTED_CALLABLE_PREFIX
from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    TrajectorySpec,
    run_canonical_online_trajectory_case,
    run_native_trajectory_case,
)


RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_4-runner"
PERMIT = ExecutionPermit("V11A_DEVELOPMENT_REGRESSION", True)
FRAMEWORKS = {
    "OA": "OpenAI Agents SDK",
    "MS": "Microsoft Agent Framework",
}


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def make_cases(framework_code: str, family: str, repetition: int, depth: int):
    framework = FRAMEWORKS[framework_code]
    cases = []
    for index in range(depth):
        effect = "IDEMPOTENT_EFFECT" if depth == 2 and index == 1 else "READ_ONLY"
        capability = "tool.idem" if effect == "IDEMPOTENT_EFFECT" else "tool.read"
        case = tool_case(
            f"DEV-RC-{framework_code}{depth}-{repetition:03d}-{index:02d}",
            framework,
            effect_semantics=effect,
        )
        cases.append(
            replace(
                case,
                arguments={"city": f"{family.lower()}-{repetition:03d}-{index:02d}"},
                capability=capability,
            )
        )
    return tuple(cases)


def identity_manifest() -> dict[str, Any]:
    workflows = []
    for code, framework in FRAMEWORKS.items():
        for repetition in range(100):
            cases = make_cases(code, "DUPLICATE_NAME_CAUSAL", repetition, 2)
            workflows.append(
                {
                    "workflow_id": f"DEV-RC-{code}-DUP2-{repetition:03d}",
                    "family": "DUPLICATE_NAME_CAUSAL",
                    "framework": framework,
                    "depth": 2,
                    "operation_ids": [case.operation_id for case in cases],
                    "logical_action_names": [case.logical_action_name for case in cases],
                }
            )
        for depth, count in ((10, 30), (30, 10)):
            for repetition in range(count):
                cases = make_cases(code, f"REPEATED_TARGET_{depth}", repetition, depth)
                workflows.append(
                    {
                        "workflow_id": f"DEV-RC-{code}-REPEAT{depth}-{repetition:03d}",
                        "family": "LONG_REPEATED_TARGET",
                        "framework": framework,
                        "depth": depth,
                        "operation_ids": [case.operation_id for case in cases],
                        "logical_action_names": [case.logical_action_name for case in cases],
                    }
                )
    manifest = {
        "schema": "AgentTool.V12RCFreshRoutingStressIdentities/1",
        "development_only": True,
        "old_v12_final_identities_excluded": [
            "DEV-V12-FINAL-causal-1",
            "DEV-V12-FINAL-causal-2",
        ],
        "workflow_count": len(workflows),
        "duplicate_name_causal": 200,
        "long_repeated_target": 80,
        "workflows": workflows,
        "selected_v12_cases_executed": 0,
    }
    manifest["identity_aggregate_sha256"] = sha256_json(workflows)
    return manifest


class WarningCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def assert_projection(value: dict[str, Any], manifest: dict[str, Any]) -> None:
    trajectory = value["projection"]["trajectory"]
    expected = list(manifest["operation_ids"])
    actual = [str(item["operation_id"]) for item in trajectory]
    if Counter(expected) != Counter(actual) or len(set(actual)) != len(expected):
        raise AssertionError(f"operation-ID fidelity failure: expected={expected!r} actual={actual!r}")
    if [item["logical_action"] for item in trajectory] != manifest["logical_action_names"]:
        raise AssertionError("logical action identity changed during framework routing")
    if len(trajectory) != int(manifest["depth"]):
        raise AssertionError("framework trajectory length mismatch")
    if PRIVATE_ROUTED_CALLABLE_PREFIX in json.dumps(value, sort_keys=True):
        raise AssertionError("private routed callable alias entered semantic evidence")


def cases_for_manifest(item: dict[str, Any]):
    code = "OA" if item["framework"] == FRAMEWORKS["OA"] else "MS"
    family = "DUPLICATE_NAME_CAUSAL" if item["family"] == "DUPLICATE_NAME_CAUSAL" else f"REPEATED_TARGET_{item['depth']}"
    repetition = int(item["workflow_id"].rsplit("-", 1)[1])
    cases = make_cases(code, family, repetition, int(item["depth"]))
    if [case.operation_id for case in cases] != item["operation_ids"]:
        raise AssertionError("frozen stress identity did not reconstruct exactly")
    return cases


def execute(root: Path, runner: Path) -> None:
    manifest_path = root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = identity_manifest()
    if manifest != expected:
        raise AssertionError("frozen stress identity manifest changed before execution")
    write_json_exclusive(
        root / "execution_started.json",
        {
            "identity_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "selected_v12_cases_executed": 0,
        },
    )
    results = []
    capture = WarningCapture()
    logging.getLogger().addHandler(capture)
    try:
        for index, item in enumerate(manifest["workflows"]):
            cases = cases_for_manifest(item)
            spec = TrajectorySpec(
                item["workflow_id"], item["framework"], "DYNAMIC_SEQUENCE", cases
            )
            before_warning_count = len(capture.messages)
            native = run_native_trajectory_case(spec, PERMIT)
            canonical = run_canonical_online_trajectory_case(
                spec,
                root / "raw" / f"{index:03d}-{item['workflow_id']}",
                PERMIT,
                runner_binary=runner,
            )
            assert_projection(native, item)
            assert_projection(canonical["semantic"], item)
            if native["projection"] != canonical["semantic"]["projection"]:
                raise AssertionError("native/canonical repeated-name semantic mismatch")
            if not canonical["causal_proof"]["passed"]:
                raise AssertionError("canonical causal proof failed")
            public_views = {
                "raw_trace": canonical["raw_trace"],
                "structural": canonical["strict_structural_projection"],
                "size": canonical["strict_size_projection"],
            }
            if PRIVATE_ROUTED_CALLABLE_PREFIX in json.dumps(public_views, sort_keys=True):
                raise AssertionError("private routed callable alias entered public evidence")
            new_warnings = capture.messages[before_warning_count:]
            if any("Tool name collision detected" in message for message in new_warnings):
                raise AssertionError("framework emitted a Tool name collision warning")
            results.append(
                {
                    "workflow_id": item["workflow_id"],
                    "family": item["family"],
                    "framework": item["framework"],
                    "depth": item["depth"],
                    "passed": True,
                    "operation_id_count": len(item["operation_ids"]),
                    "causal_proof": True,
                    "private_alias_in_public_view": False,
                    "tool_name_collision_warning": False,
                }
            )
            if (index + 1) % 10 == 0:
                print(f"V12_RC_ROUTING_STRESS {index + 1}/{len(manifest['workflows'])}", flush=True)
    finally:
        logging.getLogger().removeHandler(capture)
    duplicate = [row for row in results if row["family"] == "DUPLICATE_NAME_CAUSAL"]
    long_target = [row for row in results if row["family"] == "LONG_REPEATED_TARGET"]
    by_framework = {
        framework: sum(row["passed"] for row in duplicate if row["framework"] == framework)
        for framework in FRAMEWORKS.values()
    }
    write_json_exclusive(
        root / "result.json",
        {
            "schema": "AgentTool.V12RCRoutingStressResult/1",
            "identity_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "workflow_results": results,
            "duplicate_name_causal_passed": sum(row["passed"] for row in duplicate),
            "duplicate_name_causal_total": len(duplicate),
            "duplicate_name_by_framework": by_framework,
            "long_repeated_target_passed": sum(row["passed"] for row in long_target),
            "long_repeated_target_total": len(long_target),
            "private_routing_alias_in_public_view": False,
            "selected_v12_cases_executed": 0,
            "status": "PASS",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--freeze-identities", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.freeze_identities == args.execute:
        raise ValueError("choose exactly one of --freeze-identities or --execute")
    if args.freeze_identities:
        if args.output.exists():
            raise FileExistsError("V12-RC stress output root already exists")
        args.output.mkdir(parents=True)
        write_json_exclusive(args.output / "identity_manifest.json", identity_manifest())
        return
    execute(args.output, args.runner)


if __name__ == "__main__":
    main()
