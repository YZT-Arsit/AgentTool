from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_3_profile_closure import execute_once, strict_cases
from scripts.run_v11_4_profile_qualification import freeze_harness, write_json
from v11_4.profile import selected_profile
from v11_online.session import CanonicalOnlineSession, OnlineSessionFailure


RESULTS = ROOT / "results_v11_4_development"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def repaired_agent_identity(runner: Path, profile) -> dict[str, Any]:
    root = RESULTS / "post_gate_repair_raw" / "agent_identity_v2"
    framework = "OpenAI Agents SDK"
    arm_a_cases = strict_cases(5, "v114-final-agent-identity-v2-a")
    arm_b_cases = [
        replace(case, agent_id=1, agent_capability="agent.a", capability="tool.a")
        for case in strict_cases(5, "v114-final-agent-identity-v2-b")
    ]
    a = execute_once(root / "A", runner, profile, framework, "DYNAMIC_SEQUENCE", arm_a_cases)
    b = execute_once(root / "B", runner, profile, framework, "DYNAMIC_SEQUENCE", arm_b_cases)
    structural_equal = a.get("strict_structural_projection") == b.get("strict_structural_projection")
    size_equal = a.get("strict_size_projection") == b.get("strict_size_projection")
    return {
        "pair": "AGENT_IDENTITY",
        "version": "V2_FRESH_NON_HOLDOUT_REPAIR",
        "passed": bool(a.get("passed") and b.get("passed") and structural_equal and size_equal),
        "arm_a_functional": bool(a.get("passed")),
        "arm_b_functional": bool(b.get("passed")),
        "structural_equal": structural_equal,
        "size_equal": size_equal,
        "arm_a_private_agent": "agent.tools/10",
        "arm_b_private_agent": "agent.a/1",
        "effect_class": "READ_ONLY",
        "arm_a_error": a.get("error", ""),
        "arm_b_error": b.get("error", ""),
        "holdout": False,
    }


def repaired_finite_horizon(runner: Path, profile) -> dict[str, Any]:
    root = RESULTS / "post_gate_repair_raw" / "finite_horizon_v3"
    summary = root / "negative_summary.json"
    if summary.is_file():
        return json.loads(summary.read_text(encoding="utf-8"))
    if root.exists():
        raise RuntimeError("interrupted V11.4 finite-horizon repair is not retried")
    case = strict_cases(1, "v114-final-finite-horizon-v3")[0]
    session = CanonicalOnlineSession(root, [case], runner_binary=runner, public_profile=profile)
    rejected = ""
    with session:
        # RunOnline assigns public T0 exactly 50 public periods after emitting
        # SESSION_READY.  Waiting H + 50*Delta + 100 ms therefore makes the
        # action ready 100 ms after the public admission horizon, while still
        # leaving 460 ms of the fixed public schedule for rejection/closure.
        ready_after_ready_ms = profile.admission_horizon_ms + 50 * profile.round_period_ms + 100
        time.sleep(ready_after_ready_ms / 1000)
        try:
            session.submit(case, case.argument_schema.validate_values(case.arguments))
        except OnlineSessionFailure as exc:
            rejected = str(exc)
    assert session.trace is not None
    trace = session.trace
    events = trace["public_relay_events"]
    value = {
        "version": "V3_FRESH_NON_HOLDOUT_REPAIR",
        "passed": all(
            (
                rejected == "PROFILE_ADMISSION_CLOSED",
                trace["session_status"] == "COMPLETE",
                len(events) == profile.total_rounds,
                int(trace["provider_invocations"]) == 0,
                int(trace["dummy_provider_operations"]) == 0,
                int(trace["admitted"]) == 0,
                len({event["relay_client_connection_id"] for event in events}) == 1,
                len({event["relay_gateway_connection_id"] for event in events}) == 1,
            )
        ),
        "private_outcome": rejected,
        "public_start_lead_periods": 50,
        "fixed_ready_after_public_horizon_ms": 100,
        "fixed_wait_after_session_ready_ms": profile.admission_horizon_ms + 50 * profile.round_period_ms + 100,
        "public_rounds": len(events),
        "public_sessions": 1,
        "provider_invocations": int(trace["provider_invocations"]),
        "dummy_provider_operations": int(trace["dummy_provider_operations"]),
        "scheduled_lifetime_ms": profile.scheduled_lifetime_ms,
        "holdout": False,
    }
    write_json(summary, value)
    return value


def main() -> None:
    if (ROOT / "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json").exists():
        raise FileExistsError("V11.4 harness is already frozen; repair runner refuses post-freeze execution")
    runner = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_4-runner"
    profile = selected_profile(10, 3000)
    old_gate = json.loads((RESULTS / "v11_4_gate_summary.json").read_text(encoding="utf-8"))
    if old_gate.get("gates", {}).get("finite_horizon_fail_closed") is not False:
        raise AssertionError("post-gate repair requires a preserved finite-horizon failure")

    repaired_pair = repaired_agent_identity(runner, profile)
    repaired_negative = repaired_finite_horizon(runner, profile)

    old_rows = list(csv.DictReader((RESULTS / "structural_regression.csv").open(encoding="utf-8")))
    effective_rows: list[dict[str, Any]] = []
    for row in old_rows:
        if row["pair"] == "AGENT_IDENTITY":
            effective_rows.append(repaired_pair)
        else:
            effective_rows.append(row)
    write_csv(RESULTS / "structural_regression_effective.csv", effective_rows)

    gates = dict(old_gate["gates"])
    gates["structural_regression"] = bool(repaired_pair["passed"] and len(effective_rows) == 12 and all(str(row["passed"]).lower() == "true" for row in effective_rows))
    gates["finite_horizon_fail_closed"] = bool(repaired_negative["passed"])
    passed = all(gates.values())
    final = {
        **old_gate,
        "schema": "AgentTool.V11_4GateSummaryAfterFreshTestConstructionRepairs/1",
        "pre_repair_gate_summary": old_gate,
        "post_gate_repairs": {
            "agent_identity": repaired_pair,
            "finite_horizon": repaired_negative,
            "old_failed_arms_retried": False,
            "fresh_non_holdout_cases": True,
        },
        "gates": gates,
        "all_gates_pass": passed,
        "online_admission_profile": "PASS" if passed else "FAIL",
        "original_software_design_scope_complete": "YES" if passed else "NO",
        "ready_for_v11a_fresh_holdout_freeze": "YES" if passed else "NO",
        "holdout_selected_or_executed": False,
    }
    write_json(RESULTS / "v11_4_gate_summary.json", final)
    write_json(RESULTS / "post_gate_repair_summary.json", final["post_gate_repairs"])
    if passed:
        freeze_harness(runner, profile)


if __name__ == "__main__":
    main()
