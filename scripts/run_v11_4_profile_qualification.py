from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_2_online_development import agent, tools
from scripts.run_v11_3_profile_closure import (
    admission_closed_negative,
    execute_once,
    mixed_cases,
    strict_cases,
    structural_specs,
    summary_row,
)
from v11_4.profile import (
    HORIZON_CANDIDATES_MS,
    PERIOD_CANDIDATES_MS,
    OnlinePublicProfileV11_4,
    horizon_candidate_profiles,
    period_candidate_profiles,
    selected_profile,
)
from v11_full_scope.fixtures import SCHEMAS_AND_VALUES
from v11_full_scope.models import AgentServiceSubtype


PERIOD_SESSIONS = 500
HORIZON_COUNTS = {10: 100, 20: 50, 30: 30, 50: 30}
MIXED_FAMILIES = (
    "TOOL_TO_TOOL",
    "TOOL_TO_AGENT_AS_TOOL",
    "AGENT_AS_TOOL_TO_TOOL",
    "TOOL_TO_HANDOFF",
    "MICROSOFT_TOOL_TO_AGENT_AS_TOOL",
    "INTERNAL_TO_EXTERNAL",
    "EXTERNAL_TO_INTERNAL",
    "STRUCTURED_TOOL_TO_AGENT_AS_TOOL",
)


def write_json(path: Path, value: Any, *, immutable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if immutable and path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite different frozen artifact: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def host_record(runner: Path) -> dict[str, Any]:
    commands = {
        "kernel": ["uname", "-a"],
        "cpu": ["sh", "-c", "lscpu | sed -n '1,24p'"],
        "go": ["go", "version"],
        "python": [sys.executable, "--version"],
        "load": ["sh", "-c", "cat /proc/loadavg 2>/dev/null || true"],
    }
    value: dict[str, Any] = {
        "platform": platform.platform(),
        "runner": str(runner),
        "runner_sha256": sha256(runner),
        "development_only": True,
        "holdout_selected_or_executed": False,
    }
    for key, command in commands.items():
        try:
            value[key] = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as exc:
            value[key] = f"UNAVAILABLE: {exc}"
    return value


def _period_selected(output: Path) -> OnlinePublicProfileV11_4 | None:
    path = output / "period_selection.json"
    if not path.is_file():
        return None
    selected = json.loads(path.read_text(encoding="utf-8")).get("selected_profile")
    if not selected:
        return None
    return OnlinePublicProfileV11_4(
        profile_id=selected["profile_id"],
        maximum_real_operations=int(selected["maximum_real_operations"]),
        admission_horizon_ms=int(selected["admission_horizon_ms"]),
        round_period_ms=int(selected["round_period_ms"]),
    ).validate()


def qualify_period(output: Path, runner: Path) -> OnlinePublicProfileV11_4 | None:
    all_rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    selected: OnlinePublicProfileV11_4 | None = None
    for profile in period_candidate_profiles():
        rows: list[dict[str, Any]] = []
        for iteration in range(PERIOD_SESSIONS):
            cases = strict_cases(1, f"v114-final-period-p{profile.round_period_ms}-{iteration:03d}")
            raw = output / "period_raw" / f"P{profile.round_period_ms}" / f"{iteration:03d}"
            value = execute_once(raw, runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases)
            row = summary_row("PERIOD", iteration, value, period_ms=profile.round_period_ms)
            rows.append(row)
            all_rows.append(row)
            if (iteration + 1) % 25 == 0 or iteration + 1 == PERIOD_SESSIONS:
                print(
                    f"PERIOD P={profile.round_period_ms} completed={iteration + 1}/{PERIOD_SESSIONS} "
                    f"passed={sum(bool(item['passed']) for item in rows)}",
                    flush=True,
                )
        passed = len(rows) == PERIOD_SESSIONS and all(row["passed"] for row in rows)
        outcomes.append(
            {
                "period_ms": profile.round_period_ms,
                "sessions": len(rows),
                "passed_sessions": sum(bool(row["passed"]) for row in rows),
                "scheduler_misses": sum(int(row["schedule_misses"]) for row in rows),
                "transport_or_other_failures": sum(bool(row["error"]) for row in rows),
                "profile_overflow": sum(int(row["profile_overflow"]) for row in rows),
                "dummy_heavy_ops": sum(int(row["dummy_heavy_ops"]) for row in rows),
                "silent_committed_result_loss": sum(int(row["silent_committed_result_loss"]) for row in rows),
                "passed": passed,
                "selected": passed,
            }
        )
        write_csv(output / "period_qualification.csv", all_rows)
        write_json(
            output / "period_selection.json",
            {
                "schema": "AgentTool.V11_4PeriodSelection/1",
                "candidate_order_ms": list(PERIOD_CANDIDATES_MS),
                "selection_rule": "smallest candidate passing all 500 independent sessions; stop after first pass",
                "candidate_outcomes": outcomes,
                "selected_profile": profile.public_schema() if passed else None,
                "timing_privacy": "OPEN / NOT TESTED",
            },
        )
        if passed:
            selected = profile
            break
    return selected


def freeze_horizon_candidates(period_ms: int) -> None:
    value = {
        "schema": "AgentTool.V11_4OnlineHorizonCandidates/1",
        "selected_period_ms": period_ms,
        "candidate_order_ms": list(HORIZON_CANDIDATES_MS),
        "selection_rule": "smallest horizon in ascending predeclared order passing every causal-depth stratum",
        "qualification_counts": {str(k): v for k, v in HORIZON_COUNTS.items()},
        "profiles": [profile.public_schema() for profile in horizon_candidate_profiles(period_ms)],
        "candidates_changed_after_execution": False,
        "holdout_selected_or_executed": False,
    }
    write_json(ROOT / "ONLINE_HORIZON_CANDIDATES_V11_4.json", value, immutable=True)


def _horizon_selected(output: Path) -> OnlinePublicProfileV11_4 | None:
    path = output / "horizon_selection.json"
    if not path.is_file():
        return None
    item = json.loads(path.read_text(encoding="utf-8")).get("selected_final_profile")
    if not item:
        return None
    return selected_profile(int(item["round_period_ms"]), int(item["admission_horizon_ms"]))


def qualify_horizon(output: Path, runner: Path, period_ms: int) -> OnlinePublicProfileV11_4 | None:
    all_rows: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    selected: OnlinePublicProfileV11_4 | None = None
    for profile in horizon_candidate_profiles(period_ms):
        rows: list[dict[str, Any]] = []
        for count, repetitions in HORIZON_COUNTS.items():
            for iteration in range(repetitions):
                cases = strict_cases(count, f"v114-horizon-h{profile.admission_horizon_ms}-c{count}-{iteration:03d}")
                raw = output / "horizon_raw" / f"H{profile.admission_horizon_ms}" / f"causal_{count}" / f"{iteration:03d}"
                value = execute_once(raw, runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases)
                row = summary_row(
                    f"CAUSAL_{count}", iteration, value,
                    horizon_ms=profile.admission_horizon_ms,
                    admission_rounds=profile.admission_rounds,
                )
                rows.append(row)
                all_rows.append(row)
                if (iteration + 1) % 10 == 0 or iteration + 1 == repetitions:
                    print(
                        f"HORIZON H={profile.admission_horizon_ms} causal={count} "
                        f"completed={iteration + 1}/{repetitions} "
                        f"passed={sum(bool(item['passed']) for item in rows if item['group'] == f'CAUSAL_{count}')}",
                        flush=True,
                    )
        passed = len(rows) == sum(HORIZON_COUNTS.values()) and all(row["passed"] for row in rows)
        outcomes.append(
            {
                "horizon_ms": profile.admission_horizon_ms,
                "admission_rounds": profile.admission_rounds,
                "total_rounds": profile.total_rounds,
                "scheduled_lifetime_ms": profile.scheduled_lifetime_ms,
                "sessions": len(rows),
                "passed_sessions": sum(bool(row["passed"]) for row in rows),
                "scheduler_misses": sum(int(row["schedule_misses"]) for row in rows),
                "resolved_not_admitted": sum(int(row["resolved_not_admitted"]) for row in rows),
                "strata": {
                    str(count): {
                        "passed": sum(bool(row["passed"]) for row in rows if row["group"] == f"CAUSAL_{count}"),
                        "total": sum(row["group"] == f"CAUSAL_{count}" for row in rows),
                    }
                    for count in HORIZON_COUNTS
                },
                "passed": passed,
                "selected": passed,
            }
        )
        final = selected_profile(period_ms, profile.admission_horizon_ms) if passed else None
        write_csv(output / "horizon_qualification.csv", all_rows)
        write_json(
            output / "horizon_selection.json",
            {
                "schema": "AgentTool.V11_4HorizonSelection/1",
                "candidate_order_ms": list(HORIZON_CANDIDATES_MS),
                "selected_period_ms": period_ms,
                "candidate_outcomes": outcomes,
                "selected_final_profile": final.public_schema() if final is not None else None,
                "holdout_selected_or_executed": False,
            },
        )
        if passed:
            selected = final
            break
    return selected


def mixed_spec(kind: str, label: str) -> tuple[str, str, list[Any]]:
    if kind == "MICROSOFT_TOOL_TO_AGENT_AS_TOOL":
        framework = "Microsoft Agent Framework"
        cases = tools(label + "-tool", framework, ["tool.read"]) + [
            agent(label + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL)
        ]
        return framework, "TOOL_TO_AGENT_AS_TOOL", cases
    return mixed_cases(kind, label)


def qualify_mixed(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in MIXED_FAMILIES:
        for iteration in range(30):
            framework, workflow, cases = mixed_spec(kind, f"v114-mixed-{kind.lower()}-{iteration:03d}")
            value = execute_once(output / "mixed_raw" / kind.lower() / f"{iteration:03d}", runner, profile, framework, workflow, cases)
            rows.append(summary_row(kind, iteration, value))
        print(f"MIXED {kind} passed={sum(bool(r['passed']) for r in rows if r['group'] == kind)}/30", flush=True)
    write_csv(output / "mixed_qualification.csv", rows)
    return rows


def robustness(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pir_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for delay in (0, 10, 25, 50):
        for iteration in range(20):
            value = execute_once(
                output / "pir_delay_raw" / f"delay_{delay}" / f"{iteration:03d}", runner, profile,
                "OpenAI Agents SDK", "DYNAMIC_SEQUENCE",
                strict_cases(10, f"v114-pir-delay-{delay}-{iteration:03d}"), pir_delay_ms=delay,
            )
            pir_rows.append(summary_row(f"PIR_DELAY_{delay}", iteration, value, private_delay_ms=delay))
    for delay in (0, 5, 10, 20):
        for iteration in range(20):
            value = execute_once(
                output / "decision_delay_raw" / f"delay_{delay}" / f"{iteration:03d}", runner, profile,
                "OpenAI Agents SDK", "DYNAMIC_SEQUENCE",
                strict_cases(10, f"v114-decision-delay-{delay}-{iteration:03d}"), decision_delay_ms=delay,
            )
            decision_rows.append(summary_row(f"DECISION_DELAY_{delay}", iteration, value, private_delay_ms=delay))
    write_csv(output / "pir_delay_robustness.csv", pir_rows)
    write_csv(output / "decision_delay_robustness.csv", decision_rows)
    return pir_rows, decision_rows


def invariants(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    action_rows: list[dict[str, Any]] = []
    action_values: list[dict[str, Any]] = []
    for count in (1, 2, 5, 10, 20, 30, 50):
        value = execute_once(
            output / "action_count_raw" / f"count_{count}", runner, profile,
            "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(count, f"v114-count-{count}"),
        )
        action_values.append(value)
        action_rows.append(summary_row("ACTION_COUNT", count, value, actual_actions=count))
    structural = action_values[0].get("strict_structural_projection")
    size = action_values[0].get("strict_size_projection")
    for row, value in zip(action_rows, action_values, strict=True):
        row["structural_equal"] = value.get("strict_structural_projection") == structural
        row["size_equal"] = value.get("strict_size_projection") == size
        row["invariant_pass"] = bool(row["passed"] and row["structural_equal"] and row["size_equal"])

    depth_rows: list[dict[str, Any]] = []
    depth_values: list[dict[str, Any]] = []
    for label, workflow, strict in (
        ("DEPTH_10", "DYNAMIC_SEQUENCE", True),
        ("DEPTH_1", "PARALLEL_ACTIONS", False),
        ("DEPTH_2", "MIXED_PARALLEL", False),
    ):
        value = execute_once(
            output / "causal_depth_raw" / label.lower(), runner, profile,
            "OpenAI Agents SDK", workflow, strict_cases(10, f"v114-depth-{label.lower()}"),
            require_strict_causal=strict,
        )
        depth_values.append(value)
        depth_rows.append(summary_row("CAUSAL_DEPTH", len(depth_rows), value, causal_depth=label))
    structural = depth_values[0].get("strict_structural_projection")
    size = depth_values[0].get("strict_size_projection")
    for row, value in zip(depth_rows, depth_values, strict=True):
        row["structural_equal"] = value.get("strict_structural_projection") == structural
        row["size_equal"] = value.get("strict_size_projection") == size
        row["invariant_pass"] = bool(row["passed"] and row["structural_equal"] and row["size_equal"])
    write_csv(output / "action_count_invariant.csv", action_rows)
    write_csv(output / "causal_depth_invariant.csv", depth_rows)
    return action_rows, depth_rows


def semantic_regression(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> list[dict[str, Any]]:
    specs: list[tuple[str, str, str, list[Any]]] = []
    for kind in MIXED_FAMILIES:
        framework, workflow, cases = mixed_spec(kind, f"v114-sem-{kind.lower()}")
        specs.append((kind, framework, workflow, cases))
    specs.append(("STRICT_CAUSAL_10", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(10, "v114-sem-causal10")))
    specs.append(("MICROSOFT_CAUSAL_3", "Microsoft Agent Framework", "DYNAMIC_SEQUENCE", strict_cases(3, "v114-sem-ms3", "Microsoft Agent Framework")))
    rows: list[dict[str, Any]] = []
    for index, (label, framework, workflow, cases) in enumerate(specs):
        value = execute_once(
            output / "semantic_raw" / label.lower(), runner, profile, framework, workflow, cases,
            compare_native=True,
        )
        rows.append(summary_row(label, index, value))
    write_csv(output / "semantic_regression.csv", rows)
    return rows


def structural_regression(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, (workflow_a, cases_a), (workflow_b, cases_b) in structural_specs():
        a = execute_once(
            output / "structural_raw" / name.lower() / "A", runner, profile,
            "OpenAI Agents SDK", workflow_a, cases_a, require_strict_causal=workflow_a == "DYNAMIC_SEQUENCE",
        )
        b = execute_once(
            output / "structural_raw" / name.lower() / "B", runner, profile,
            "OpenAI Agents SDK", workflow_b, cases_b, require_strict_causal=workflow_b == "DYNAMIC_SEQUENCE",
        )
        structural_equal = a.get("strict_structural_projection") == b.get("strict_structural_projection")
        size_equal = a.get("strict_size_projection") == b.get("strict_size_projection")
        rows.append(
            {
                "pair": name,
                "passed": bool(a.get("passed") and b.get("passed") and structural_equal and size_equal),
                "arm_a_functional": a.get("passed", False),
                "arm_b_functional": b.get("passed", False),
                "structural_equal": structural_equal,
                "size_equal": size_equal,
                "arm_a_error": a.get("error", ""),
                "arm_b_error": b.get("error", ""),
            }
        )
    write_csv(output / "structural_regression.csv", rows)
    return rows


def final_reliability(output: Path, runner: Path, profile: OnlinePublicProfileV11_4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    causal_counts = {10: 100, 20: 50, 30: 50, 50: 50}
    for count, repetitions in causal_counts.items():
        for iteration in range(repetitions):
            value = execute_once(
                output / "final_raw" / f"causal_{count}" / f"{iteration:03d}", runner, profile,
                "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(count, f"v114-final-c{count}-{iteration:03d}"),
            )
            rows.append(summary_row(f"CAUSAL_{count}", iteration, value))
        print(f"FINAL causal={count} passed={sum(bool(r['passed']) for r in rows if r['group'] == f'CAUSAL_{count}')}/{repetitions}", flush=True)

    mixed_kinds = ("TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL", "TOOL_TO_HANDOFF", "MICROSOFT_TOOL_TO_AGENT_AS_TOOL")
    for kind in mixed_kinds:
        for iteration in range(25):
            framework, workflow, cases = mixed_spec(kind, f"v114-final-mixed-{kind.lower()}-{iteration:03d}")
            value = execute_once(output / "final_raw" / "mixed" / kind.lower() / f"{iteration:03d}", runner, profile, framework, workflow, cases)
            rows.append(summary_row("MIXED_AGENT_TRAJECTORY", iteration, value, family=kind))
    for kind in ("INTERNAL_TO_EXTERNAL", "EXTERNAL_TO_INTERNAL"):
        for iteration in range(25):
            framework, workflow, cases = mixed_spec(kind, f"v114-final-ie-{kind.lower()}-{iteration:03d}")
            value = execute_once(output / "final_raw" / "internal_external" / kind.lower() / f"{iteration:03d}", runner, profile, framework, workflow, cases)
            rows.append(summary_row("INTERNAL_EXTERNAL_MIXED", iteration, value, family=kind))
    for iteration in range(50):
        framework, workflow, cases = mixed_spec("STRUCTURED_TOOL_TO_AGENT_AS_TOOL", f"v114-final-structured-{iteration:03d}")
        value = execute_once(output / "final_raw" / "structured" / f"{iteration:03d}", runner, profile, framework, workflow, cases)
        rows.append(summary_row("STRUCTURED_MULTI_ARGUMENT", iteration, value))
    write_csv(output / "final_reliability.csv", rows)
    return rows


def freeze_harness(runner: Path, profile: OnlinePublicProfileV11_4) -> None:
    paths = (
        "v11_online/session.py",
        "v11_online/frameworks.py",
        "v11_4/profile.py",
        "scripts/freeze_v11_4_profile_candidates.py",
        "scripts/run_v11_4_profile_qualification.py",
        "scripts/run_v11_4_post_gate_repairs.py",
        "common_action_gateway_v2/canonicalv9/online.go",
        "common_action_gateway_v2/v9ohttp/ohttp_backend.go",
        "canonical_v9_1/projection.py",
        "PUBLIC_PROFILE_ONLINE_V11_4.json",
    )
    value = {
        "schema": "AgentTool.V11_4OnlineExecutionHarnessFreeze/1",
        "selected_profile": profile.public_schema(),
        "files_sha256": {name: sha256(ROOT / name) for name in paths},
        "final_linux_binary": {"path": str(runner), "sha256": sha256(runner)},
        "old_v10_selected_outcomes_observed": False,
        "v10_1_selected_outcomes_observed": False,
        "holdout_selected_or_executed": False,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
    }
    write_json(ROOT / "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json", value, immutable=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--phase", choices=("period", "horizon", "post", "all"), default="all")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "qualification_host.json", host_record(args.runner))

    period = _period_selected(args.output)
    if args.phase in {"period", "all"} and period is None:
        period = qualify_period(args.output, args.runner)
    if period is None:
        write_json(args.output / "v11_4_gate_summary.json", {"public_period_qualification": "FAIL", "holdout_selected_or_executed": False})
        return
    write_json(ROOT / "PUBLIC_PERIOD_SELECTION_V11_4.json", json.loads((args.output / "period_selection.json").read_text(encoding="utf-8")))
    freeze_horizon_candidates(period.round_period_ms)
    if args.phase == "period":
        return

    profile = _horizon_selected(args.output)
    if args.phase in {"horizon", "all"} and profile is None:
        profile = qualify_horizon(args.output, args.runner, period.round_period_ms)
    if profile is None:
        write_json(args.output / "v11_4_gate_summary.json", {"public_period_qualification": "PASS", "online_admission_horizon_qualified": "FAIL", "holdout_selected_or_executed": False})
        return
    write_json(ROOT / "ONLINE_HORIZON_SELECTION_V11_4.json", json.loads((args.output / "horizon_selection.json").read_text(encoding="utf-8")))
    write_json(ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json", profile.public_schema(), immutable=True)
    if args.phase == "horizon":
        return

    mixed = qualify_mixed(args.output, args.runner, profile)
    pir_rows, decision_rows = robustness(args.output, args.runner, profile)
    action_rows, depth_rows = invariants(args.output, args.runner, profile)
    negative = admission_closed_negative(args.output, args.runner, profile)
    semantic_rows = semantic_regression(args.output, args.runner, profile)
    structural_rows = structural_regression(args.output, args.runner, profile)
    final_rows = final_reliability(args.output, args.runner, profile)
    gates = {
        "public_period_qualification": True,
        "online_admission_horizon_qualified": True,
        "mixed_causal_families": bool(mixed and all(row["passed"] for row in mixed)),
        "pir_delay_robustness": bool(pir_rows and all(row["passed"] for row in pir_rows)),
        "decision_delay_robustness": bool(decision_rows and all(row["passed"] for row in decision_rows)),
        "action_count_invariant": bool(action_rows and all(row["invariant_pass"] for row in action_rows)),
        "causal_depth_invariant": bool(depth_rows and all(row["invariant_pass"] for row in depth_rows)),
        "finite_horizon_fail_closed": bool(negative["passed"]),
        "semantic_regression": bool(semantic_rows and all(row["passed"] for row in semantic_rows)),
        "structural_regression": bool(structural_rows and all(row["passed"] for row in structural_rows)),
        "final_reliability": bool(final_rows and all(row["passed"] for row in final_rows)),
    }
    passed = all(gates.values())
    write_json(
        args.output / "v11_4_gate_summary.json",
        {
            "selected_profile": profile.public_schema(),
            "gates": gates,
            "all_gates_pass": passed,
            "online_admission_profile": "PASS" if passed else "FAIL",
            "original_software_design_scope_complete": "YES" if passed else "NO",
            "ready_for_v11a_fresh_holdout_freeze": "YES" if passed else "NO",
            "holdout_selected_or_executed": False,
        },
    )
    if passed:
        freeze_harness(args.runner, profile)


if __name__ == "__main__":
    main()
