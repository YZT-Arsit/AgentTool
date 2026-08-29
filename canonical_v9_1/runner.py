from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from canonical_v9.runner import GO_RUNNER, Providers, route_specs

from .profile import PublicCapacityProfile


def invoke_go_with_public_profile(
    output: Path,
    profile: PublicCapacityProfile,
    private_actions: list[dict[str, object]],
    providers: Providers,
    *,
    runner_binary: Path | None = None,
    plan_overrides: Mapping[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Run V9 with a profile selected independently of private actions."""

    selected_runner = runner_binary or GO_RUNNER
    if not selected_runner.is_file():
        raise FileNotFoundError(f"canonical Go runner is missing: {selected_runner}")
    profile.validate()
    profile.admit(len(private_actions))
    output.mkdir(parents=True, exist_ok=False)
    plan = profile.go_plan_fields()
    plan.update(
        {
            "state_directory": str(output / "gateway_state"),
            "routes": route_specs(providers),
            "actions": private_actions,
        }
    )
    if plan_overrides:
        allowed = {
            "round_period_ms",
            "scheduler_tolerance_ms",
            "fault_delay_response_slot",
            "fault_delay_response_ms",
            "fault_scheduler_stall_slot",
            "fault_scheduler_stall_ms",
        }
        unknown = set(plan_overrides) - allowed
        if unknown:
            raise ValueError(f"unsupported canonical development override: {sorted(unknown)}")
        plan.update(plan_overrides)
    plan_path = output / "trusted_private_plan.json"
    result_path = output / "go_canonical_result.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    invocation_start_ns = time.monotonic_ns()
    completed = subprocess.run(
        [str(selected_runner), "--plan", str(plan_path), "--output", str(result_path)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )
    invocation_end_ns = time.monotonic_ns()
    (output / "go_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "go_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"canonical Go runner failed: {completed.stderr}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    metadata = {
        "profile_selected_before_private_execution": True,
        "public_profile_id": profile.profile_id,
        "public_maximum_real_operations": profile.maximum_real_operations,
        "private_actual_real_actions": len(private_actions),
        "public_scheduled_start_policy": profile.scheduled_start_policy,
        "public_scheduled_lifetime_ns": profile.scheduled_lifetime_ns,
        "wrapper_invocation_start_monotonic_ns": invocation_start_ns,
        "wrapper_invocation_end_monotonic_ns": invocation_end_ns,
        "wrapper_elapsed_ns": invocation_end_ns - invocation_start_ns,
        "connection_close_slip_status": "NOT_CAPTURED_BY_FROZEN_V9_RUNNER",
        "timing_privacy": "OPEN / NOT_TESTED",
        "canonical_runner_binary": str(selected_runner),
        "session_status": result.get("session_status", "LEGACY_NO_EXPLICIT_STATUS"),
    }
    (output / "public_schedule_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    if result.get("session_status") not in {None, "COMPLETE"}:
        raise RuntimeError(
            f"canonical session failed explicitly: {result['session_status']}; "
            f"raw result preserved at {result_path}"
        )
    return result, metadata
