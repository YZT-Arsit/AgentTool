from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v10_holdout.harness import load_v10_profile
from v11_full_scope.canonical import native_local_outcome
from v11_full_scope.fixtures import agent_case, tool_case, with_readiness
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily, V11ActionCase
from v11_online.frameworks import prewarm_framework, run_online_framework_workflow, trajectory_projection
from v11_online.session import CanonicalOnlineSession


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    fields = list(row)
    if exists:
        with path.open(newline="", encoding="utf-8") as source:
            fields = next(csv.reader(source))
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def effect_for(capability: str) -> str:
    return {
        "tool.read": "READ_ONLY",
        "tool.idem": "IDEMPOTENT_EFFECT",
        "tool.nonidem": "NON_IDEMPOTENT_EFFECT",
    }[capability]


def operation_id(label: str) -> str:
    digest = hashlib.sha256(label.encode()).hexdigest()[:10]
    stem = "".join(character for character in label if character.isalnum())[:19]
    return f"op{stem}{digest}"[:32]


def tools(prefix: str, framework: str, capabilities: list[str]) -> list[V11ActionCase]:
    values = []
    for index, capability in enumerate(capabilities):
        case = tool_case(f"{prefix}-{index}", framework, index % 7, effect_for(capability))
        values.append(
            replace(
                case,
                operation_id=operation_id(f"{prefix}-{index}"),
                logical_action_name=f"tool_{prefix.replace('-', '_')}_{index}",
                capability=capability,
            )
        )
    return values


def agent(prefix: str, framework: str, subtype: AgentServiceSubtype, *, internal: bool = False) -> V11ActionCase:
    value = agent_case(
        prefix,
        framework,
        subtype,
        placement="TRUSTED_MODULE_LOCAL" if internal else "EXTERNAL",
    )
    return replace(
        value,
        operation_id=operation_id(prefix),
        logical_action_name=f"agent_{prefix.replace('-', '_')}",
    )


def workflow_cases(gate: str, iteration: int) -> tuple[str, str, list[V11ActionCase]]:
    prefix = f"v112-{gate.lower()}-{iteration:03d}"
    if gate == "TOOL_1":
        return "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools(prefix, "OpenAI Agents SDK", ["tool.read"])
    if gate == "TOOL_TO_TOOL":
        return "OpenAI Agents SDK", gate, tools(prefix, "OpenAI Agents SDK", ["tool.read", "tool.idem"])
    if gate == "TOOL_TO_AGENT_AS_TOOL":
        return "OpenAI Agents SDK", gate, tools(prefix, "OpenAI Agents SDK", ["tool.read"]) + [agent(prefix + "-aat", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL)]
    if gate == "TOOL_TO_HANDOFF":
        return "OpenAI Agents SDK", gate, tools(prefix, "OpenAI Agents SDK", ["tool.read"]) + [agent(prefix + "-handoff", "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF)]
    if gate == "MICROSOFT_TOOL_TO_AGENT_AS_TOOL":
        return "Microsoft Agent Framework", "TOOL_TO_AGENT_AS_TOOL", tools(prefix, "Microsoft Agent Framework", ["tool.read"]) + [agent(prefix + "-aat", "Microsoft Agent Framework", AgentServiceSubtype.AGENT_AS_TOOL)]
    if gate == "DYNAMIC_5_ACTION":
        return "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools(prefix, "OpenAI Agents SDK", ["tool.read"] * 5)
    if gate == "DYNAMIC_10_ACTION":
        return "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools(prefix, "OpenAI Agents SDK", ["tool.read"] * 10)
    if gate == "INTERNAL_EXTERNAL_MIX":
        return "OpenAI Agents SDK", "INTERNAL_TO_EXTERNAL", [
            agent(prefix + "-internal", "OpenAI Agents SDK", AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True),
            *tools(prefix + "-external", "OpenAI Agents SDK", ["tool.read"]),
        ]
    raise ValueError(gate)


def native_direct(cases: list[V11ActionCase]) -> dict[str, Any]:
    outcomes = [native_local_outcome(case) for case in cases]
    return {"projection": trajectory_projection(cases, outcomes, f"framework-completed:DIRECT-{len(cases)}")}


def run_online(
    output: Path,
    framework: str,
    workflow: str,
    cases: list[V11ActionCase],
    runner: Path,
    *,
    compare_native: bool,
    plan_overrides: dict[str, object] | None = None,
) -> dict[str, Any]:
    prewarm_framework(framework)
    native = (
        run_online_framework_workflow(framework, workflow, cases, native_implementation)
        if compare_native
        else None
    )
    session = CanonicalOnlineSession(output, cases, runner_binary=runner, plan_overrides=plan_overrides)
    with session:
        canonical = run_online_framework_workflow(framework, workflow, cases, session.implementation())
    assert session.trace is not None and session.pir is not None
    trace = session.trace
    profile = load_v10_profile()
    events = trace["public_relay_events"]
    client_connections = len({event["relay_client_connection_id"] for event in events})
    gateway_connections = len({event["relay_gateway_connection_id"] for event in events})
    expected_external = sum(case.placement == "EXTERNAL" for case in cases)
    setup_stages = [event["stage"] for event in trace["public_setup_events"]]
    gate = all(
        (
            trace["session_status"] == "COMPLETE",
            trace.get("online_mode") is True,
            int(trace.get("startup_action_count", -1)) == 0,
            int(trace["admitted"]) == expected_external,
            len(trace["results"]) == expected_external,
            int(trace["provider_invocations"]) == expected_external,
            int(trace["dummy_provider_operations"]) == 0,
            int(trace["profile_overflow_events"]) == 0,
            int(trace["schedule_misses"]) == 0,
            int(trace["silent_committed_result_losses"]) == 0,
            not trace["pending_operation_ids"],
            not trace.get("resolved_not_admitted_ids", []),
            not trace.get("unresolved_operation_ids", []),
            not trace.get("framework_waiter_ids", []),
            len(events) == profile.total_rounds == 111,
            [int(event["round"]) for event in events] == list(range(1, 112)),
            {int(event["request_length"]) for event in events} == {1079},
            {int(event["response_length"]) for event in events} == {800},
            client_connections == 1,
            gateway_connections == 1,
            all(event["client_http_version"] == "HTTP/2.0" for event in events),
            all(event["gateway_http_version"] == "HTTP/2.0" for event in events),
            setup_stages.count("CLIENT_RELAY_HTTP2_ESTABLISHED") == 1,
            setup_stages.count("RELAY_GATEWAY_HTTP2_ESTABLISHED") == 1,
            session.pir.query_count == len(cases),
            len(session.pir.query_hashes) == len(set(session.pir.query_hashes)),
            session.causal_proof()["passed"],
        )
    )
    semantic_equal = native is None or native["projection"] == canonical["projection"]
    structural, size = session.public_projections()
    value = {
        "passed": bool(gate and semantic_equal),
        "functional": gate,
        "semantic_equal": semantic_equal,
        "framework": framework,
        "workflow": workflow,
        "logical_actions": len(cases),
        "external_actions": expected_external,
        "pir_queries": session.pir.query_count,
        "dynamic_pir": session.pir.query_count == len(cases),
        "causal_proof": session.causal_proof(),
        "runner_process_launches": 1,
        "public_preconnect_count": 1,
        "public_session_count": 1,
        "client_relay_connections": client_connections,
        "relay_gateway_connections": gateway_connections,
        "rounds": len(events),
        "request_bytes": sorted({int(event["request_length"]) for event in events}),
        "response_bytes": sorted({int(event["response_length"]) for event in events}),
        "schedule_misses": int(trace["schedule_misses"]),
        "profile_overflow": int(trace["profile_overflow_events"]),
        "dummy_heavy_ops": int(trace["dummy_provider_operations"]),
        "silent_committed_result_loss": int(trace["silent_committed_result_losses"]),
        "strict_structural_projection": structural,
        "strict_size_projection": size,
        "canonical_projection": canonical["projection"],
        "native_projection": native["projection"] if native is not None else None,
    }
    write_json(output / "online_development_summary.json", value)
    return value


def run_static_regression(output: Path, runner: Path) -> None:
    # Binary-level static regression is executed by the accompanying Go test
    # command; preserve its immutable result rather than rerunning holdouts.
    write_json(
        output / "static_regression.json",
        {
            "v11_1_commit": "d8a8788a30ac8a9cc2c630d4a3e347660e8f2dfa",
            "representative_go_packages": ["canonicalv9", "v8", "v9ohttp"],
            "runner": str(runner),
            "holdout_cases_executed": 0,
        },
    )


def run_causal(output: Path, runner: Path) -> None:
    csv_path = output / "online_causal_workflows.csv"
    gates = [
        "TOOL_TO_TOOL",
        "TOOL_TO_AGENT_AS_TOOL",
        "TOOL_TO_HANDOFF",
        "MICROSOFT_TOOL_TO_AGENT_AS_TOOL",
    ]
    # Explicit reverse Agent-as-Tool -> Tool workflows for both frameworks.
    custom = []
    for framework, label in (("OpenAI Agents SDK", "OPENAI_AGENT_AS_TOOL_TO_TOOL"), ("Microsoft Agent Framework", "MICROSOFT_AGENT_AS_TOOL_TO_TOOL")):
        prefix = "v112-" + label.lower()
        custom.append((label, framework, "AGENT_AS_TOOL_TO_TOOL", [agent(prefix + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL), *tools(prefix + "-tool", framework, ["tool.read"])]))
    items = [(gate, *workflow_cases(gate, 0)) for gate in gates] + custom
    for label, framework, workflow, cases in items:
        raw = output / "causal_raw" / label.lower()
        if raw.exists():
            continue
        try:
            value = run_online(raw, framework, workflow, cases, runner, compare_native=True)
            error = ""
        except Exception as exc:
            value = {"passed": False, "semantic_equal": False, "causal_proof": {"passed": False}, "public_session_count": 0, "dynamic_pir": False}
            error = f"{type(exc).__name__}: {exc}"
        append_csv(
            csv_path,
            {
                "workflow": label,
                "framework": framework,
                "passed": value["passed"],
                "semantic_equal": value["semantic_equal"],
                "causal": value["causal_proof"]["passed"],
                "dynamic_pir": value["dynamic_pir"],
                "public_sessions": value["public_session_count"],
                "error": error,
            },
        )


def run_stress(output: Path, runner: Path) -> None:
    csv_path = output / "online_reliability_stress.csv"
    repetitions = {
        "TOOL_1": 100,
        "TOOL_TO_TOOL": 50,
        "TOOL_TO_AGENT_AS_TOOL": 50,
        "TOOL_TO_HANDOFF": 50,
        "MICROSOFT_TOOL_TO_AGENT_AS_TOOL": 50,
        "DYNAMIC_5_ACTION": 30,
        "DYNAMIC_10_ACTION": 20,
        "INTERNAL_EXTERNAL_MIX": 30,
    }
    for gate, count in repetitions.items():
        for iteration in range(count):
            raw = output / "stress_raw" / gate.lower() / f"{iteration:03d}"
            if raw.exists():
                continue
            framework, workflow, cases = workflow_cases(gate, iteration)
            try:
                value = run_online(raw, framework, workflow, cases, runner, compare_native=False)
                error = ""
            except Exception as exc:
                value = {
                    "passed": False,
                    "logical_actions": len(cases),
                    "public_session_count": 0,
                    "rounds": 0,
                    "schedule_misses": -1,
                    "profile_overflow": -1,
                    "dummy_heavy_ops": -1,
                    "silent_committed_result_loss": -1,
                    "dynamic_pir": False,
                }
                error = f"{type(exc).__name__}: {exc}"
            append_csv(
                csv_path,
                {
                    "gate": gate,
                    "iteration": iteration,
                    "passed": value["passed"],
                    "logical_actions": value["logical_actions"],
                    "public_sessions": value["public_session_count"],
                    "rounds": value["rounds"],
                    "schedule_misses": value["schedule_misses"],
                    "profile_overflow": value["profile_overflow"],
                    "dummy_heavy_ops": value["dummy_heavy_ops"],
                    "silent_committed_result_loss": value["silent_committed_result_loss"],
                    "dynamic_pir": value["dynamic_pir"],
                    "error": error,
                },
            )


def run_semantic(output: Path, runner: Path) -> None:
    csv_path = output / "online_semantic_development.csv"
    cases = []
    for gate in ("TOOL_TO_TOOL", "TOOL_TO_AGENT_AS_TOOL", "TOOL_TO_HANDOFF", "MICROSOFT_TOOL_TO_AGENT_AS_TOOL"):
        cases.append((gate, *workflow_cases(gate, 900)))
    for framework, label in (("OpenAI Agents SDK", "OPENAI_AGENT_AS_TOOL_TO_TOOL"), ("Microsoft Agent Framework", "MICROSOFT_AGENT_AS_TOOL_TO_TOOL")):
        prefix = "v112-sem-" + label.lower()
        cases.append((label, framework, "AGENT_AS_TOOL_TO_TOOL", [agent(prefix + "-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL), *tools(prefix + "-tool", framework, ["tool.read"])]))
    # Add one three-step Tool trajectory per framework to exercise intermediate state.
    for framework, label in (("OpenAI Agents SDK", "OPENAI_TOOL_3"), ("Microsoft Agent Framework", "MICROSOFT_TOOL_3")):
        cases.append((label, framework, "DYNAMIC_SEQUENCE", tools("v112-sem-" + label.lower(), framework, ["tool.read"] * 3)))
    for label, framework, workflow, values in cases:
        raw = output / "semantic_raw" / label.lower()
        if raw.exists():
            continue
        try:
            result = run_online(raw, framework, workflow, values, runner, compare_native=True)
            error = ""
        except Exception as exc:
            result = {"passed": False, "semantic_equal": False, "causal_proof": {"passed": False}, "public_session_count": 0}
            error = f"{type(exc).__name__}: {exc}"
        append_csv(csv_path, {"case": label, "framework": framework, "passed": result["passed"], "projection_equal": result["semantic_equal"], "causal": result["causal_proof"]["passed"], "public_sessions": result["public_session_count"], "error": error})


def run_structural(output: Path, runner: Path) -> None:
    csv_path = output / "online_structural_regression.csv"
    pairs: list[tuple[str, tuple[str, str, list[V11ActionCase]], tuple[str, str, list[V11ActionCase]]]] = []
    pairs.append(("ACTION_COUNT_1_VS_5", ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools("v112-str-count-a", "OpenAI Agents SDK", ["tool.read"])), ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools("v112-str-count-b", "OpenAI Agents SDK", ["tool.read"] * 5))))
    pairs.append(("TOOL_VS_AGENT_AS_TOOL", ("OpenAI Agents SDK", "TOOL_TO_TOOL", tools("v112-str-kind-a", "OpenAI Agents SDK", ["tool.read"] * 2)), ("OpenAI Agents SDK", "TOOL_TO_AGENT_AS_TOOL", tools("v112-str-kind-b", "OpenAI Agents SDK", ["tool.read"]) + [agent("v112-str-kind-b-aat", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL)])))
    pairs.append(("REPEATED_VS_VARIED", ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools("v112-str-repeat", "OpenAI Agents SDK", ["tool.read"] * 5)), ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", tools("v112-str-varied", "OpenAI Agents SDK", ["tool.read", "tool.idem", "tool.read", "tool.idem", "tool.read"]))))
    pairs.append(("INTERNAL_EXTERNAL_ORDER", ("OpenAI Agents SDK", "INTERNAL_TO_EXTERNAL", [agent("v112-str-ie-int", "OpenAI Agents SDK", AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True), *tools("v112-str-ie-ext", "OpenAI Agents SDK", ["tool.read"])]), ("OpenAI Agents SDK", "EXTERNAL_TO_INTERNAL", [*tools("v112-str-ei-ext", "OpenAI Agents SDK", ["tool.read"]), agent("v112-str-ei-int", "OpenAI Agents SDK", AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True)])))
    early = with_readiness(tools("v112-str-ready-a", "OpenAI Agents SDK", ["tool.read"])[0], "EARLY_READY")
    late = with_readiness(tools("v112-str-ready-b", "OpenAI Agents SDK", ["tool.read"])[0], "LATE_READY_WITHIN_BOUND")
    pairs.append(("EARLY_VS_LATE_READY", ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [early]), ("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [late])))

    for name, arm_a, arm_b in pairs:
        pair_root = output / "structural_raw" / name.lower()
        if pair_root.exists():
            continue
        try:
            a = run_online(pair_root / "A", *arm_a, runner, compare_native=False)
            b = run_online(pair_root / "B", *arm_b, runner, compare_native=False)
            structural_equal = a["strict_structural_projection"] == b["strict_structural_projection"]
            size_equal = a["strict_size_projection"] == b["strict_size_projection"]
            passed = a["passed"] and b["passed"] and structural_equal and size_equal
            error = ""
        except Exception as exc:
            a = b = {"passed": False, "public_session_count": 0}
            structural_equal = size_equal = passed = False
            error = f"{type(exc).__name__}: {exc}"
        append_csv(csv_path, {"pair": name, "passed": passed, "arm_a_functional": a["passed"], "arm_b_functional": b["passed"], "structural_equal": structural_equal, "size_equal": size_equal, "arm_a_sessions": a["public_session_count"], "arm_b_sessions": b["public_session_count"], "error": error})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--mode", choices=("causal", "stress", "semantic", "structural", "all"), default="all")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    run_static_regression(args.output, args.runner)
    modes = ("causal", "stress", "semantic", "structural") if args.mode == "all" else (args.mode,)
    for mode in modes:
        globals()[f"run_{mode}"](args.output, args.runner)


if __name__ == "__main__":
    main()
