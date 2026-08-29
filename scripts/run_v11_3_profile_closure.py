from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_2_online_development import agent, operation_id, tools
from v11_3.experiment import run_online_development
from v11_3.profile import OnlinePublicProfile, candidate_profiles
from v11_full_scope.fixtures import SCHEMAS_AND_VALUES, with_readiness
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily, V11ActionCase
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession, OnlineSessionFailure


QUALIFICATION_COUNTS = {10: 100, 20: 50, 30: 30, 50: 20}
FINAL_MIXED_COUNTS = {
    "TOOL_TO_AGENT_AS_TOOL": 30,
    "AGENT_AS_TOOL_TO_TOOL": 30,
    "TOOL_TO_HANDOFF": 30,
    "INTERNAL_EXTERNAL_MIX": 30,
}
MIXED_CLASSES = (
    "TOOL_TO_TOOL",
    "TOOL_TO_AGENT_AS_TOOL",
    "AGENT_AS_TOOL_TO_TOOL",
    "TOOL_TO_HANDOFF",
    "INTERNAL_TO_EXTERNAL",
    "EXTERNAL_TO_INTERNAL",
    "STRUCTURED_TOOL_TO_AGENT_AS_TOOL",
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def strict_cases(count: int, label: str, framework: str = "OpenAI Agents SDK") -> list[V11ActionCase]:
    return tools(label, framework, ["tool.read"] * count)


def composite_agent_tools(count: int, label: str) -> list[V11ActionCase]:
    return [
        replace(case, agent_id=21, agent_capability="agent.workflow.21")
        for case in strict_cases(count, label)
    ]


def mixed_cases(kind: str, label: str) -> tuple[str, str, list[V11ActionCase]]:
    framework = "OpenAI Agents SDK"
    if kind == "TOOL_TO_TOOL":
        return framework, "TOOL_TO_TOOL", tools(label, framework, ["tool.read", "tool.idem"])
    if kind == "TOOL_TO_AGENT_AS_TOOL":
        return framework, kind, tools(label + "-tool", framework, ["tool.read"]) + [agent(label + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL)]
    if kind == "AGENT_AS_TOOL_TO_TOOL":
        return framework, kind, [agent(label + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL)] + tools(label + "-tool", framework, ["tool.read"])
    if kind == "TOOL_TO_HANDOFF":
        return framework, kind, tools(label + "-tool", framework, ["tool.read"]) + [agent(label + "-handoff", framework, AgentServiceSubtype.HANDOFF)]
    if kind == "INTERNAL_TO_EXTERNAL":
        return framework, kind, [agent(label + "-internal", framework, AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True)] + tools(label + "-external", framework, ["tool.read"])
    if kind == "EXTERNAL_TO_INTERNAL":
        return framework, kind, tools(label + "-external", framework, ["tool.read"]) + [agent(label + "-internal", framework, AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True)]
    if kind == "STRUCTURED_TOOL_TO_AGENT_AS_TOOL":
        structured = tools(label + "-structured", framework, ["tool.read"])[0]
        structured = replace(
            structured,
            argument_schema=SCHEMAS_AND_VALUES[6][0],
            arguments=SCHEMAS_AND_VALUES[6][1],
        )
        return framework, "TOOL_TO_AGENT_AS_TOOL", [structured, agent(label + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL)]
    raise ValueError(kind)


def summary_row(group: str, iteration: int, value: dict[str, Any], **extra: Any) -> dict[str, Any]:
    gate = value.get("trace_gate", {})
    return {
        "group": group,
        "iteration": iteration,
        "passed": value.get("passed", False),
        "profile_id": value.get("profile_id", ""),
        "logical_actions": value.get("logical_actions", 0),
        "framework": value.get("framework", ""),
        "workflow": value.get("workflow", ""),
        "public_sessions": value.get("public_session_count", 0),
        "rounds": gate.get("rounds", 0),
        "schedule_misses": gate.get("schedule_misses", -1),
        "profile_overflow": gate.get("profile_overflow", -1),
        "dummy_heavy_ops": gate.get("dummy_heavy_ops", -1),
        "silent_committed_result_loss": gate.get("silent_committed_result_loss", -1),
        "resolved_not_admitted": gate.get("resolved_not_admitted", -1),
        "dynamic_pir": value.get("dynamic_pir", False),
        "causal": value.get("causal_proof", {}).get("passed", False),
        "semantic_equal": value.get("semantic_equal", False),
        "error": value.get("error", ""),
        **extra,
    }


def execute_once(
    raw: Path,
    runner: Path,
    profile: OnlinePublicProfile,
    framework: str,
    workflow: str,
    cases: list[V11ActionCase],
    *,
    compare_native: bool = False,
    require_strict_causal: bool = True,
    pir_delay_ms: int = 0,
    decision_delay_ms: int = 0,
) -> dict[str, Any]:
    summary = raw / "v11_3_development_summary.json"
    if summary.is_file():
        return json.loads(summary.read_text(encoding="utf-8"))
    if raw.exists():
        value = {
            "passed": False,
            "error": "INTERRUPTED_DEVELOPMENT_RUN_NOT_RETRIED",
            "framework": framework,
            "workflow": workflow,
            "profile_id": profile.profile_id,
            "logical_actions": len(cases),
            "public_session_count": 0,
            "dynamic_pir": False,
            "causal_proof": {"passed": False},
            "semantic_equal": False,
            "trace_gate": {},
        }
        write_json(summary, value)
        return value
    return run_online_development(
        raw, framework, workflow, cases, runner, profile,
        compare_native=compare_native,
        require_strict_causal=require_strict_causal,
        pir_delay_ms=pir_delay_ms,
        decision_delay_ms=decision_delay_ms,
    )


def qualify_candidates(output: Path, runner: Path) -> OnlinePublicProfile | None:
    all_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    selected: OnlinePublicProfile | None = None
    for profile in candidate_profiles():
        candidate_rows: list[dict[str, Any]] = []
        for count, repetitions in QUALIFICATION_COUNTS.items():
            for iteration in range(repetitions):
                label = f"v113-qual-a{profile.admission_rounds}-c{count}-{iteration:03d}"
                cases = strict_cases(count, label)
                raw = output / "qualification_raw" / f"A{profile.admission_rounds}" / f"causal_{count}" / f"{iteration:03d}"
                value = execute_once(raw, runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases)
                row = summary_row(f"CAUSAL_{count}", iteration, value, admission_rounds=profile.admission_rounds)
                candidate_rows.append(row)
                all_rows.append(row)
                if (iteration + 1) % 10 == 0 or iteration + 1 == repetitions:
                    print(
                        f"QUALIFY A={profile.admission_rounds} causal={count} "
                        f"completed={iteration + 1}/{repetitions} "
                        f"passed={sum(bool(item['passed']) for item in candidate_rows if item['group'] == f'CAUSAL_{count}')}",
                        flush=True,
                    )
        passed = len(candidate_rows) == sum(QUALIFICATION_COUNTS.values()) and all(row["passed"] for row in candidate_rows)
        decisions.append({
            "admission_rounds": profile.admission_rounds,
            "sessions": len(candidate_rows),
            "passed_sessions": sum(bool(row["passed"]) for row in candidate_rows),
            "passed": passed,
            "selected": passed,
        })
        write_csv(output / "candidate_qualification.csv", all_rows)
        write_json(output / "candidate_selection_progress.json", {"decisions": decisions, "selected": profile.public_schema() if passed else None})
        print(f"CANDIDATE A={profile.admission_rounds} passed={passed} sessions={len(candidate_rows)}", flush=True)
        if passed:
            selected = profile
            break
    return selected


def qualify_mixed(output: Path, runner: Path, profile: OnlinePublicProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in MIXED_CLASSES:
        for iteration in range(30):
            framework, workflow, cases = mixed_cases(kind, f"v113-mixed-{kind.lower()}-{iteration:03d}")
            value = execute_once(output / "mixed_qualification_raw" / kind.lower() / f"{iteration:03d}", runner, profile, framework, workflow, cases, compare_native=False)
            rows.append(summary_row(kind, iteration, value))
    write_csv(output / "mixed_qualification.csv", rows)
    return rows


def robustness(output: Path, runner: Path, profile: OnlinePublicProfile) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pir_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for delay in (0, 10, 25, 50):
        for iteration in range(20):
            cases = strict_cases(10, f"v113-pir-delay-{delay}-{iteration:03d}")
            value = execute_once(output / "pir_delay_raw" / f"delay_{delay}" / f"{iteration:03d}", runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases, pir_delay_ms=delay)
            pir_rows.append(summary_row(f"PIR_DELAY_{delay}", iteration, value, private_delay_ms=delay))
    for delay in (0, 5, 10, 20):
        for iteration in range(20):
            cases = strict_cases(10, f"v113-decision-delay-{delay}-{iteration:03d}")
            value = execute_once(output / "decision_delay_raw" / f"delay_{delay}" / f"{iteration:03d}", runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases, decision_delay_ms=delay)
            decision_rows.append(summary_row(f"DECISION_DELAY_{delay}", iteration, value, private_delay_ms=delay))
    write_csv(output / "pir_delay_robustness.csv", pir_rows)
    write_csv(output / "decision_delay_robustness.csv", decision_rows)
    return pir_rows, decision_rows


def invariant_run(output: Path, runner: Path, profile: OnlinePublicProfile) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    action_rows: list[dict[str, Any]] = []
    action_values: list[dict[str, Any]] = []
    for count in (1, 2, 5, 10, 20, 30, 50):
        value = execute_once(output / "action_count_raw" / f"count_{count}", runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(count, f"v113-count-{count}"))
        action_values.append(value)
        action_rows.append(summary_row("ACTION_COUNT", count, value, actual_actions=count))
    baseline_structural = action_values[0].get("strict_structural_projection")
    baseline_size = action_values[0].get("strict_size_projection")
    for row, value in zip(action_rows, action_values, strict=True):
        row["structural_equal"] = value.get("strict_structural_projection") == baseline_structural
        row["size_equal"] = value.get("strict_size_projection") == baseline_size
        row["invariant_pass"] = bool(row["passed"] and row["structural_equal"] and row["size_equal"])

    depth_rows: list[dict[str, Any]] = []
    depth_values: list[dict[str, Any]] = []
    for label, workflow, strict in (
        ("DEPTH_10", "DYNAMIC_SEQUENCE", True),
        ("DEPTH_1", "PARALLEL_ACTIONS", False),
        ("DEPTH_2", "MIXED_PARALLEL", False),
    ):
        value = execute_once(output / "causal_depth_raw" / label.lower(), runner, profile, "OpenAI Agents SDK", workflow, strict_cases(10, f"v113-depth-{label.lower()}"), require_strict_causal=strict)
        depth_values.append(value)
        depth_rows.append(summary_row("CAUSAL_DEPTH", len(depth_rows), value, causal_depth=label))
    baseline_structural = depth_values[0].get("strict_structural_projection")
    baseline_size = depth_values[0].get("strict_size_projection")
    for row, value in zip(depth_rows, depth_values, strict=True):
        row["structural_equal"] = value.get("strict_structural_projection") == baseline_structural
        row["size_equal"] = value.get("strict_size_projection") == baseline_size
        row["invariant_pass"] = bool(row["passed"] and row["structural_equal"] and row["size_equal"])
    write_csv(output / "action_count_invariant.csv", action_rows)
    write_csv(output / "causal_depth_invariant.csv", depth_rows)
    return action_rows, depth_rows


def admission_closed_negative(output: Path, runner: Path, profile: OnlinePublicProfile) -> dict[str, Any]:
    raw = output / "admission_closed_negative_raw"
    summary = raw / "negative_summary.json"
    if summary.is_file():
        return json.loads(summary.read_text(encoding="utf-8"))
    if raw.exists():
        raise RuntimeError("interrupted admission-closed negative test is not retried")
    case = strict_cases(1, "v113-admission-closed-negative")[0]
    session = CanonicalOnlineSession(raw, [case], runner_binary=runner, public_profile=profile)
    rejected = ""
    with session:
        time.sleep((profile.admission_horizon_ms + 10) / 1000)
        try:
            session.submit(case, case.argument_schema.validate_values(case.arguments))
        except OnlineSessionFailure as exc:
            rejected = str(exc)
    assert session.trace is not None
    trace = session.trace
    events = trace["public_relay_events"]
    value = {
        "passed": all((
            rejected == "PROFILE_ADMISSION_CLOSED",
            trace["session_status"] == "COMPLETE",
            len(events) == profile.total_rounds,
            int(trace["provider_invocations"]) == 0,
            int(trace["dummy_provider_operations"]) == 0,
            int(trace["admitted"]) == 0,
            len({event["relay_client_connection_id"] for event in events}) == 1,
            len({event["relay_gateway_connection_id"] for event in events}) == 1,
        )),
        "private_outcome": rejected,
        "public_rounds": len(events),
        "public_sessions": 1,
        "provider_invocations": int(trace["provider_invocations"]),
        "dummy_provider_operations": int(trace["dummy_provider_operations"]),
        "scheduled_lifetime_ms": profile.scheduled_lifetime_ms,
        "holdout": False,
    }
    write_json(summary, value)
    return value


def final_reliability(output: Path, runner: Path, profile: OnlinePublicProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for count, repetitions in QUALIFICATION_COUNTS.items():
        for iteration in range(repetitions):
            cases = strict_cases(count, f"v113-final-c{count}-{iteration:03d}")
            value = execute_once(output / "final_reliability_raw" / f"causal_{count}" / f"{iteration:03d}", runner, profile, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases)
            rows.append(summary_row(f"CAUSAL_{count}", iteration, value))
    for kind, repetitions in FINAL_MIXED_COUNTS.items():
        for iteration in range(repetitions):
            mixed_kind = "INTERNAL_TO_EXTERNAL" if kind == "INTERNAL_EXTERNAL_MIX" else kind
            framework, workflow, cases = mixed_cases(mixed_kind, f"v113-final-{kind.lower()}-{iteration:03d}")
            value = execute_once(output / "final_reliability_raw" / kind.lower() / f"{iteration:03d}", runner, profile, framework, workflow, cases)
            rows.append(summary_row(kind, iteration, value))
    write_csv(output / "online_reliability_final.csv", rows)
    return rows


def semantic_regression(output: Path, runner: Path, profile: OnlinePublicProfile) -> list[dict[str, Any]]:
    specs: list[tuple[str, str, str, list[V11ActionCase]]] = []
    for kind in ("TOOL_TO_TOOL", "TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL", "TOOL_TO_HANDOFF", "INTERNAL_TO_EXTERNAL", "EXTERNAL_TO_INTERNAL", "STRUCTURED_TOOL_TO_AGENT_AS_TOOL"):
        framework, workflow, cases = mixed_cases(kind, f"v113-sem-{kind.lower()}")
        specs.append((kind, framework, workflow, cases))
    specs.append(("STRICT_CAUSAL_10", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(10, "v113-sem-causal-10")))
    specs.append(("MICROSOFT_CAUSAL_3", "Microsoft Agent Framework", "DYNAMIC_SEQUENCE", strict_cases(3, "v113-sem-ms-3", "Microsoft Agent Framework")))
    rows: list[dict[str, Any]] = []
    for index, (label, framework, workflow, cases) in enumerate(specs):
        value = execute_once(output / "semantic_regression_raw" / label.lower(), runner, profile, framework, workflow, cases, compare_native=True)
        rows.append(summary_row(label, index, value))
    write_csv(output / "online_semantic_regression.csv", rows)
    return rows


def structural_specs() -> list[tuple[str, tuple[str, list[V11ActionCase]], tuple[str, list[V11ActionCase]]]]:
    f = "OpenAI Agents SDK"
    early = with_readiness(strict_cases(1, "v113-str-ready-early")[0], "EARLY_READY")
    late = with_readiness(strict_cases(1, "v113-str-ready-late")[0], "LATE_READY_WITHIN_BOUND")
    long_arg = replace(strict_cases(1, "v113-str-arg-long")[0], arguments={"city": "X" * 300})
    return [
        ("AGENT_IDENTITY", ("DYNAMIC_SEQUENCE", strict_cases(5, "v113-str-agent-a")), ("DYNAMIC_SEQUENCE", composite_agent_tools(5, "v113-str-agent-b"))),
        ("TOOL_ROUTE", ("DYNAMIC_SEQUENCE", tools("v113-str-tool-a", f, ["tool.read"] * 5)), ("DYNAMIC_SEQUENCE", tools("v113-str-tool-b", f, ["tool.idem"] * 5))),
        ("ACTION_KIND", ("DYNAMIC_SEQUENCE", strict_cases(2, "v113-str-kind-a")), ("TOOL_TO_AGENT_AS_TOOL", mixed_cases("TOOL_TO_AGENT_AS_TOOL", "v113-str-kind-b")[2])),
        ("ACTION_COUNT", ("DYNAMIC_SEQUENCE", strict_cases(1, "v113-str-count-a")), ("DYNAMIC_SEQUENCE", strict_cases(50, "v113-str-count-b"))),
        ("REPETITION", ("DYNAMIC_SEQUENCE", tools("v113-str-rep-a", f, ["tool.read"] * 10)), ("DYNAMIC_SEQUENCE", tools("v113-str-rep-b", f, ["tool.read", "tool.idem"] * 5))),
        ("FREQUENCY", ("DYNAMIC_SEQUENCE", tools("v113-str-freq-a", f, ["tool.read"] * 10)), ("DYNAMIC_SEQUENCE", tools("v113-str-freq-b", f, ["tool.read"] * 9 + ["tool.idem"]))),
        ("RARE_TARGET", ("DYNAMIC_SEQUENCE", tools("v113-str-rare-a", f, ["tool.read"] * 10)), ("DYNAMIC_SEQUENCE", tools("v113-str-rare-b", f, ["tool.read"] * 9 + ["tool.idem"]))),
        ("TRANSITION_PATTERN", ("DYNAMIC_SEQUENCE", tools("v113-str-trans-a", f, ["tool.read", "tool.idem"] * 5)), ("DYNAMIC_SEQUENCE", tools("v113-str-trans-b", f, ["tool.read"] * 5 + ["tool.idem"] * 5))),
        ("ARGUMENT_LENGTH", ("DYNAMIC_SEQUENCE", strict_cases(1, "v113-str-arg-short")), ("DYNAMIC_SEQUENCE", [long_arg])),
        ("PROVIDER_READINESS", ("DYNAMIC_SEQUENCE", [early]), ("DYNAMIC_SEQUENCE", [late])),
        ("INTERNAL_EXTERNAL", ("INTERNAL_TO_EXTERNAL", mixed_cases("INTERNAL_TO_EXTERNAL", "v113-str-ie-a")[2]), ("EXTERNAL_TO_INTERNAL", mixed_cases("EXTERNAL_TO_INTERNAL", "v113-str-ie-b")[2])),
        ("CAUSAL_DEPTH", ("DYNAMIC_SEQUENCE", strict_cases(10, "v113-str-depth-a")), ("PARALLEL_ACTIONS", strict_cases(10, "v113-str-depth-b"))),
    ]


def structural_regression(output: Path, runner: Path, profile: OnlinePublicProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, (workflow_a, cases_a), (workflow_b, cases_b) in structural_specs():
        a = execute_once(output / "structural_regression_raw" / name.lower() / "A", runner, profile, "OpenAI Agents SDK", workflow_a, cases_a, require_strict_causal=workflow_a == "DYNAMIC_SEQUENCE")
        b = execute_once(output / "structural_regression_raw" / name.lower() / "B", runner, profile, "OpenAI Agents SDK", workflow_b, cases_b, require_strict_causal=workflow_b == "DYNAMIC_SEQUENCE")
        structural_equal = a.get("strict_structural_projection") == b.get("strict_structural_projection")
        size_equal = a.get("strict_size_projection") == b.get("strict_size_projection")
        rows.append({
            "pair": name,
            "passed": bool(a.get("passed") and b.get("passed") and structural_equal and size_equal),
            "arm_a_functional": a.get("passed", False),
            "arm_b_functional": b.get("passed", False),
            "structural_equal": structural_equal,
            "size_equal": size_equal,
            "arm_a_error": a.get("error", ""),
            "arm_b_error": b.get("error", ""),
        })
    write_csv(output / "online_structural_regression.csv", rows)
    return rows


def host_record(runner: Path) -> dict[str, Any]:
    commands = {
        "kernel": ["uname", "-a"],
        "cpu": ["sh", "-c", "lscpu | sed -n '1,24p'"],
        "go": ["go", "version"],
        "python": [sys.executable, "--version"],
        "load": ["sh", "-c", "cat /proc/loadavg 2>/dev/null || true"],
    }
    data: dict[str, Any] = {"platform": platform.platform(), "runner": str(runner), "runner_sha256": sha256(runner)}
    for key, command in commands.items():
        try:
            data[key] = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as exc:
            data[key] = f"UNAVAILABLE: {exc}"
    try:
        data["source_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
        data["source_dirty"] = bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        freeze = json.loads((ROOT / "V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json").read_text(encoding="utf-8"))
        data["source_commit"] = freeze["source_commit"]
        data["source_dirty"] = "TRANSFERRED_V11_3_SOURCE_OVERLAY"
    source_files = [
        ROOT / "v11_online" / "session.py",
        ROOT / "v11_online" / "frameworks.py",
        ROOT / "v11_3" / "profile.py",
        ROOT / "v11_3" / "experiment.py",
        ROOT / "scripts" / "run_v11_3_profile_closure.py",
        ROOT / "common_action_gateway_v2" / "canonicalv9" / "online.go",
    ]
    data["qualification_source_sha256"] = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in source_files
    }
    return data


def load_selected(output: Path) -> OnlinePublicProfile | None:
    path = output / "candidate_selection_progress.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("selected")
    if not value:
        return None
    return OnlinePublicProfile(profile_id=value["profile_id"], admission_rounds=int(value["admission_rounds"])).validate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--phase", choices=("qualification", "post", "all"), default="all")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "qualification_host.json", host_record(args.runner))
    selected = load_selected(args.output)
    if args.phase in {"qualification", "all"} and selected is None:
        selected = qualify_candidates(args.output, args.runner)
    if selected is None:
        write_json(args.output / "v11_3_gate_summary.json", {"selected_profile": None, "online_admission_profile": "FAIL"})
        return
    if args.phase == "qualification":
        return

    mixed = qualify_mixed(args.output, args.runner, selected)
    pir_rows, decision_rows = robustness(args.output, args.runner, selected)
    action_rows, depth_rows = invariant_run(args.output, args.runner, selected)
    negative = admission_closed_negative(args.output, args.runner, selected)
    final_rows = final_reliability(args.output, args.runner, selected)
    semantic_rows = semantic_regression(args.output, args.runner, selected)
    structural_rows = structural_regression(args.output, args.runner, selected)
    gates = {
        "mixed_qualification": bool(mixed and all(row["passed"] for row in mixed)),
        "pir_delay_robustness": bool(pir_rows and all(row["passed"] for row in pir_rows)),
        "decision_delay_robustness": bool(decision_rows and all(row["passed"] for row in decision_rows)),
        "action_count_invariant": bool(action_rows and all(row["invariant_pass"] for row in action_rows)),
        "causal_depth_invariant": bool(depth_rows and all(row["invariant_pass"] for row in depth_rows)),
        "finite_horizon_fail_closed": bool(negative["passed"]),
        "final_reliability": bool(final_rows and all(row["passed"] for row in final_rows)),
        "semantic_regression": bool(semantic_rows and all(row["passed"] for row in semantic_rows)),
        "structural_regression": bool(structural_rows and all(row["passed"] for row in structural_rows)),
    }
    write_json(args.output / "v11_3_gate_summary.json", {
        "selected_profile": selected.public_schema(),
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "online_admission_profile": "PASS" if all(gates.values()) else "FAIL",
        "online_reliability_stress": "PASS" if gates["final_reliability"] else "FAIL",
        "original_software_design_scope_complete": "YES" if all(gates.values()) else "NO",
        "ready_for_v11a_fresh_holdout_freeze": "YES" if all(gates.values()) else "NO",
        "holdout_selected_or_executed": False,
    })


if __name__ == "__main__":
    main()
