from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11a_confirmatory.orchestrator import (
    ExecutionPermit,
    load_semantic_case,
    load_structural_arm,
    load_trajectory_case,
    run_canonical_online_trajectory_case,
    run_canonical_semantic_case,
    run_native_semantic_case,
    run_native_trajectory_case,
    run_structural_arm,
)


OUTPUT_ROOT = ROOT / "results_v11b_confirmatory"
PLAN_PATH = ROOT / "V11B0_EXECUTION_PLAN.json"
BASELINE_PATH = ROOT / "V11B0_COMPOSED_BASELINE.json"
DRIVER_FREEZE_PATH = ROOT / "V11B0_ONE_SHOT_DRIVER_FREEZE.json"
SEMANTIC_MANIFESTS = (
    ("S1", ROOT / "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json"),
    ("S2", ROOT / "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json"),
    ("S4", ROOT / "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json"),
)
TRAJECTORY_MANIFEST = ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json"
STRUCTURAL_MANIFEST = ROOT / "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json"
ORDER_PATH = ROOT / "V11A_EXECUTION_ORDER.json"


class HarnessIntegrityFailure(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def canonical_sha(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_content() -> dict[str, Any]:
    semantic: dict[str, tuple[str, dict[str, Any]]] = {}
    for family, path in SEMANTIC_MANIFESTS:
        for item in load_json(path)["cases"]:
            semantic[item["case_id"]] = (family, item)
    trajectories = {
        item["trajectory_id"]: item
        for item in load_json(TRAJECTORY_MANIFEST)["trajectories"]
    }
    structural_pairs = load_json(STRUCTURAL_MANIFEST)["pairs"]
    structural: dict[str, tuple[str, dict[str, Any]]] = {}
    for pair in structural_pairs:
        for arm in pair["arms"]:
            structural[arm["arm_id"]] = (pair["pair_id"], arm)
    return {
        "semantic": semantic,
        "trajectories": trajectories,
        "structural": structural,
        "structural_pairs": structural_pairs,
    }


def build_execution_plan() -> dict[str, Any]:
    """Build the frozen plan without constructing runtime cases or permits."""

    order = load_json(ORDER_PATH)
    content = load_frozen_content()
    units: list[dict[str, Any]] = []

    def add(phase: str, family: str, role: str, target_id: str) -> None:
        index = len(units) + 1
        units.append(
            {
                "global_execution_index": index,
                "unit_id": f"V11B-U{index:03d}",
                "phase": phase,
                "family": family,
                "role": role,
                "target_id": target_id,
                "retry_allowed": False,
            }
        )

    for case_id in order["semantic_case_order"]:
        if case_id not in content["semantic"]:
            raise HarnessIntegrityFailure(f"semantic order references unknown case {case_id}")
        family = content["semantic"][case_id][0]
        add("1_SEMANTIC", family, "NATIVE", case_id)
        add("1_SEMANTIC", family, "CANONICAL", case_id)
    for trajectory_id in order["causal_trajectory_order"]:
        if trajectory_id not in content["trajectories"]:
            raise HarnessIntegrityFailure(
                f"trajectory order references unknown case {trajectory_id}"
            )
        add("2_CAUSAL_TRAJECTORY", "S3", "NATIVE", trajectory_id)
        add("2_CAUSAL_TRAJECTORY", "S3", "CANONICAL", trajectory_id)
    for arm_id in order["structural_arm_order"]:
        if arm_id not in content["structural"]:
            raise HarnessIntegrityFailure(f"structural order references unknown arm {arm_id}")
        pair_id = content["structural"][arm_id][0]
        add("3_STRUCTURAL", pair_id, "STRUCTURAL_ARM", arm_id)

    native = sum(unit["role"] == "NATIVE" for unit in units)
    canonical = sum(
        unit["role"] in {"CANONICAL", "STRUCTURAL_ARM"} for unit in units
    )
    if (len(units), native, canonical) != (158, 65, 93):
        raise HarnessIntegrityFailure("frozen execution-plan counts are not 158/65/93")
    return {
        "schema": "AgentTool.V11B0ExecutionPlan/1",
        "phase_order": [
            "semantic_case_order",
            "causal_trajectory_order",
            "structural_arm_order",
        ],
        "semantic_role_order": ["NATIVE", "CANONICAL"],
        "trajectory_role_order": ["NATIVE", "CANONICAL"],
        "structural_role_order": ["STRUCTURAL_ARM"],
        "unit_count": len(units),
        "native_units": native,
        "canonical_units": canonical,
        "automatic_retry": False,
        "selected_outcomes_observed_while_constructing_plan": False,
        "units": units,
    }


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def _git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def _tree_manifest(source: Path) -> tuple[str, int]:
    entries = []
    for path in sorted(
        (item for item in source.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(source).as_posix(),
    ):
        entries.append(
            (
                sha256(path),
                path.stat().st_size,
                path.relative_to(source).as_posix(),
            )
        )
    canonical = "".join(f"{digest} {size} {name}\n" for digest, size, name in entries)
    return sha256_bytes(canonical.encode()), len(entries)


def _verify_git_binding(binding: dict[str, Any]) -> bool:
    path = str(binding["path"])
    commit = str(binding["authoritative_commit"])
    expected_blob_sha = str(binding["git_blob_sha256"])
    blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    if sha256_bytes(blob) != expected_blob_sha:
        return False
    return (
        subprocess.run(
            ["git", "diff", "--quiet", commit, "HEAD", "--", path],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def verify_composed_baseline(
    baseline: dict[str, Any], *, runner_path: Path | None, require_runner: bool
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["baseline_status"] = baseline.get("status") == "COMPOSED_PREEXECUTION_BASELINE"
    checks["runtime_bindings"] = all(
        _verify_git_binding(item) for item in baseline["runtime_bindings"]
    )
    checks["analysis_overrides"] = all(
        _verify_git_binding(item) for item in baseline["analysis_overrides"]
    )
    checks["selection_bindings"] = all(
        _verify_git_binding(item) for item in baseline["selection_bindings"]
    )

    environment = load_json(ROOT / "V11A_EXECUTION_ENVIRONMENT_FREEZE.json")
    checks["openai_revision"] = (
        _git_head(ROOT / "external_stage10" / "openai-agents-python")
        == environment["openai_agents_sdk_revision"]
    )
    checks["microsoft_revision"] = (
        _git_head(ROOT / "external_stage9" / "agent-framework")
        == environment["microsoft_agent_framework_revision"]
    )
    checks["simplepir_revision"] = (
        _git_head(ROOT / "external_pir" / "simplepir")
        == environment["simplepir_revision"]
    )
    checks["simplepir_bridge_source"] = (
        sha256(ROOT / "pir_integration" / "simplepir_bridge" / "main.go")
        == environment["simplepir_bridge_source_sha256"]
    )
    ohttp_hash, ohttp_files = _tree_manifest(ROOT / "third_party" / "ohttp-go")
    provenance = load_json(ROOT / "OHTTP_VENDOR_PROVENANCE_V9.json")
    checks["ohttp_source_tree"] = (
        ohttp_hash == environment["ohttp_go_source_tree_sha256"]
        == provenance["source_tree_sha256"]
        and ohttp_files == provenance["source_file_count"]
    )
    profile_bindings = [
        item
        for item in baseline["runtime_bindings"]
        if item["path"] == "PUBLIC_PROFILE_ONLINE_V11_4.json"
    ]
    checks["public_profile"] = (
        len(profile_bindings) == 1 and _verify_git_binding(profile_bindings[0])
    )
    if require_runner:
        checks["canonical_linux_runner"] = bool(
            runner_path
            and runner_path.is_file()
            and sha256(runner_path) == baseline["canonical_linux_runner_sha256"]
        )
    else:
        checks["canonical_linux_runner"] = True
    return {"passed": all(checks.values()), "checks": checks}


def verify_driver_freeze() -> dict[str, Any]:
    freeze = load_json(DRIVER_FREEZE_PATH)
    checks: dict[str, bool] = {
        "freeze_status": freeze.get("status") == "FROZEN_PREEXECUTION_ONLY",
        "selected_execution_zero": freeze.get("selected_holdout_cases_executed") == 0,
        "approved_permits_zero": freeze.get("approved_v11b_execution_permits_instantiated") == 0,
    }
    expected_aggregate = freeze.get("aggregate_sha256")
    aggregate_input = dict(freeze)
    aggregate_input.pop("aggregate_sha256", None)
    checks["freeze_aggregate"] = expected_aggregate == canonical_sha(aggregate_input)
    checks["bound_files"] = all(
        (ROOT / path).is_file() and sha256(ROOT / path) == expected
        for path, expected in freeze.get("bound_files", {}).items()
    )
    return {"passed": all(checks.values()), "checks": checks}


def preflight(
    authorization_path: Path,
    runner_path: Path,
    *,
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    if not authorization_path.is_absolute():
        raise HarnessIntegrityFailure("authorization file must be outside implicit repo paths")
    authorization = load_json(authorization_path)
    if authorization.get("phase") != "V11B" or authorization.get("approved") is not True:
        raise HarnessIntegrityFailure("independent V11B authorization is absent")
    authorized_commit = str(authorization.get("authorized_v11b0_commit", ""))
    if not authorized_commit or _git("rev-parse", "HEAD") != authorized_commit:
        raise HarnessIntegrityFailure("HEAD is not the independently authorized V11B0 commit")
    if _git("status", "--porcelain"):
        raise HarnessIntegrityFailure("working tree is not clean")
    if output_root.exists():
        raise HarnessIntegrityFailure("results_v11b_confirmatory already exists")
    driver_freeze = verify_driver_freeze()
    if not driver_freeze["passed"]:
        raise HarnessIntegrityFailure(f"V11B0 driver freeze failed: {driver_freeze['checks']}")
    baseline = load_json(BASELINE_PATH)
    result = verify_composed_baseline(baseline, runner_path=runner_path, require_runner=True)
    if not result["passed"]:
        raise HarnessIntegrityFailure(f"composed baseline failed: {result['checks']}")
    if sha256(PLAN_PATH) != baseline["execution_plan_sha256"]:
        raise HarnessIntegrityFailure("execution plan hash mismatch")
    return {
        "authorization": authorization,
        "authorized_commit": authorized_commit,
        "driver_freeze_verification": driver_freeze,
        "baseline_verification": result,
    }


def mid_campaign_integrity(
    authorized_commit: str, runner_path: Path, baseline: dict[str, Any]
) -> None:
    if _git("rev-parse", "HEAD") != authorized_commit:
        raise HarnessIntegrityFailure("HEAD changed during campaign")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise HarnessIntegrityFailure("tracked files changed during campaign")
    result = verify_composed_baseline(baseline, runner_path=runner_path, require_runner=True)
    if not result["passed"]:
        raise HarnessIntegrityFailure("frozen baseline drifted during campaign")


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(_jsonable(value), handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


class AppendOnlyLedger:
    def __init__(self, path: Path):
        self.path = path
        self.previous = "0" * 64
        with path.open("x", encoding="utf-8", newline="\n"):
            pass

    def append(self, value: dict[str, Any]) -> dict[str, Any]:
        record = dict(value)
        record["previous_record_sha256"] = self.previous
        record["record_sha256"] = sha256_bytes(canonical_bytes(record))
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.previous = record["record_sha256"]
        return record


def artifact_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def classify_exception(error: BaseException, *, role: str) -> str:
    if isinstance(error, HarnessIntegrityFailure):
        return "HARNESS_INTEGRITY_FAILURE"
    if role == "NATIVE":
        return "NATIVE_REFERENCE_FAIL"
    if isinstance(error, TimeoutError):
        return "INFRASTRUCTURE_SCHEDULE_FAILURE"
    if isinstance(error, (ConnectionError, BrokenPipeError)):
        return "TRANSPORT_FAILURE"
    lowered = str(error).lower()
    if "admission" in lowered:
        return "PROFILE_ADMISSION_CLOSED"
    if any(token in lowered for token in ("schedule", "deadline", "session budget")):
        return "INFRASTRUCTURE_SCHEDULE_FAILURE"
    if any(token in lowered for token in ("transport", "connection", "relay")):
        return "TRANSPORT_FAILURE"
    return "CANONICAL_FUNCTIONAL_FAIL"


def structural_functional_valid(value: dict[str, Any], expected: int) -> bool:
    trace = value["raw_trace"]
    result_count = len(trace.get("results", []))
    accepted = len(trace.get("accepted_operation_ids", []))
    return all(
        (
            trace.get("session_status") == "COMPLETE",
            int(trace.get("admitted", -1)) == expected,
            int(trace.get("provider_invocations", -1)) == expected,
            result_count == expected,
            accepted == expected,
            not trace.get("pending_operation_ids"),
            int(trace.get("dummy_provider_operations", -1)) == 0,
            int(trace.get("profile_overflow_events", -1)) == 0,
            int(trace.get("schedule_misses", -1)) == 0,
            int(trace.get("silent_committed_result_losses", -1)) == 0,
        )
    )


def _approved_permit_after_preflight(preflight_result: dict[str, Any]) -> ExecutionPermit:
    if not preflight_result["baseline_verification"]["passed"]:
        raise HarnessIntegrityFailure("approved permit requested before successful preflight")
    return ExecutionPermit("V11B", True)


def execute_unit(
    unit: dict[str, Any],
    content: dict[str, Any],
    unit_dir: Path,
    permit: ExecutionPermit,
    runner_path: Path,
) -> tuple[str, dict[str, Any]]:
    target = unit["target_id"]
    role = unit["role"]
    if unit["phase"] == "1_SEMANTIC":
        manifest = content["semantic"][target][1]
        case = load_semantic_case(manifest)
        if role == "NATIVE":
            record = run_native_semantic_case(case, permit)
            value = {"record": _jsonable(record), "projection": record.projection()}
        else:
            record = run_canonical_semantic_case(case, unit_dir / "canonical", permit, runner_binary=runner_path)
            value = {"record": _jsonable(record), "projection": record.projection()}
            native_path = unit_dir.parent / f"V11B-U{unit['global_execution_index'] - 1:03d}" / "unit_result.json"
            if native_path.is_file():
                native = load_json(native_path)
                if native.get("projection") != value["projection"]:
                    return "SEMANTIC_MISMATCH", value
        return "PASS", value
    if unit["phase"] == "2_CAUSAL_TRAJECTORY":
        spec = load_trajectory_case(content["trajectories"][target])
        if role == "NATIVE":
            value = run_native_trajectory_case(spec, permit)
        else:
            value = run_canonical_online_trajectory_case(
                spec, unit_dir / "canonical", permit, runner_binary=runner_path
            )
            if not value["causal_proof"].get("passed"):
                return "CANONICAL_FUNCTIONAL_FAIL", value
            native_path = unit_dir.parent / f"V11B-U{unit['global_execution_index'] - 1:03d}" / "unit_result.json"
            if native_path.is_file():
                native = load_json(native_path)
                if native.get("projection") != value["semantic"].get("projection"):
                    return "SEMANTIC_MISMATCH", value
        return "PASS", value
    pair_id, manifest = content["structural"][target]
    spec = load_structural_arm(manifest)
    value = run_structural_arm(spec, unit_dir / "canonical", permit, runner_binary=runner_path)
    value["pair_id"] = pair_id
    value["functional_valid"] = structural_functional_valid(value, len(spec.actions))
    return ("PASS" if value["functional_valid"] else "CANONICAL_FUNCTIONAL_FAIL"), value


def write_structural_pair_verdicts(root: Path, content: dict[str, Any]) -> None:
    plan = load_json(PLAN_PATH)
    units = {unit["target_id"]: unit for unit in plan["units"] if unit["role"] == "STRUCTURAL_ARM"}
    for pair in content["structural_pairs"]:
        arm_values = []
        for arm in pair["arms"]:
            unit = units[arm["arm_id"]]
            path = root / unit["unit_id"] / "unit_result.json"
            arm_values.append(load_json(path) if path.is_file() else None)
        if not all(value and value.get("functional_valid") for value in arm_values):
            verdict = {"pair_id": pair["pair_id"], "status": "INVALID_FUNCTIONAL_PAIR"}
        else:
            left, right = arm_values
            prefix_equal = {
                horizon: left["structural_prefixes"][str(horizon)]
                == right["structural_prefixes"][str(horizon)]
                for horizon in (1, 10, 50, 100, 200, 300, 356)
            }
            verdict = {
                "pair_id": pair["pair_id"],
                "status": "PASS"
                if (
                    left["strict_structural_projection"]
                    == right["strict_structural_projection"]
                    and left["strict_size_projection"] == right["strict_size_projection"]
                    and all(prefix_equal.values())
                )
                else "STRUCTURAL_MISMATCH",
                "full_structural_equal": left["strict_structural_projection"]
                == right["strict_structural_projection"],
                "size_equal": left["strict_size_projection"]
                == right["strict_size_projection"],
                "prefix_equal": prefix_equal,
                "timestamps_compared": False,
            }
        write_json_exclusive(root / f"pair_{pair['pair_id']}_verdict.json", verdict)


def run_campaign(authorization_path: Path, runner_path: Path) -> int:
    try:
        checked = preflight(authorization_path, runner_path)
    except BaseException as error:
        print(f"HARNESS_INTEGRITY_FAILURE: {error}", file=sys.stderr)
        return 2

    OUTPUT_ROOT.mkdir(exist_ok=False)
    plan = load_json(PLAN_PATH)
    baseline = load_json(BASELINE_PATH)
    content = load_frozen_content()
    campaign = {
        "schema": "AgentTool.V11BCampaignManifest/1",
        "authorized_commit": checked["authorized_commit"],
        "execution_plan_sha256": sha256(PLAN_PATH),
        "composed_baseline_sha256": sha256(BASELINE_PATH),
        "unit_count": plan["unit_count"],
        "automatic_retry": False,
    }
    write_json_exclusive(OUTPUT_ROOT / "campaign_manifest.json", campaign)
    ledger = AppendOnlyLedger(OUTPUT_ROOT / "execution_ledger.jsonl")
    permit = _approved_permit_after_preflight(checked)

    for unit in plan["units"]:
        started = time.time_ns()
        unit_dir = OUTPUT_ROOT / unit["unit_id"]
        unit_dir.mkdir(exist_ok=False)
        try:
            mid_campaign_integrity(checked["authorized_commit"], runner_path, baseline)
            status, value = execute_unit(unit, content, unit_dir, permit, runner_path)
            write_json_exclusive(unit_dir / "unit_result.json", value)
        except HarnessIntegrityFailure as error:
            status = "HARNESS_INTEGRITY_FAILURE"
            write_json_exclusive(unit_dir / "failure.json", {"class": status, "message": str(error)})
            ledger.append(
                {
                    **unit,
                    "start_diagnostic_ns": started,
                    "end_diagnostic_ns": time.time_ns(),
                    "status_class": status,
                    "output_directory": unit_dir.relative_to(ROOT).as_posix(),
                    "artifact_hashes": artifact_hashes(unit_dir),
                }
            )
            return 3
        except BaseException as error:
            status = classify_exception(error, role=unit["role"])
            write_json_exclusive(
                unit_dir / "failure.json",
                {"class": status, "exception_type": type(error).__name__, "message": str(error)},
            )
        ledger.append(
            {
                **unit,
                "start_diagnostic_ns": started,
                "end_diagnostic_ns": time.time_ns(),
                "status_class": status,
                "output_directory": unit_dir.relative_to(ROOT).as_posix(),
                "artifact_hashes": artifact_hashes(unit_dir),
            }
        )
    write_structural_pair_verdicts(OUTPUT_ROOT, content)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen V11B one-shot confirmatory driver")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--runner", type=Path)
    args = parser.parse_args()
    if args.plan_only:
        plan = build_execution_plan()
        print(
            json.dumps(
                {
                    "unit_count": plan["unit_count"],
                    "native_units": plan["native_units"],
                    "canonical_units": plan["canonical_units"],
                    "selected_execution": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.authorization is None or args.runner is None:
        print("HARNESS_INTEGRITY_FAILURE: execution requires authorization and runner", file=sys.stderr)
        return 2
    return run_campaign(args.authorization.resolve(), args.runner.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
