from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v10_holdout.harness import load_v10_profile
from v11_full_scope.canonical import (
    canonical_external_outcome,
    canonical_internal_outcome,
    canonical_mixed_workflow,
    canonical_multi_action,
    public_projections,
)
from v11_full_scope.fixtures import SCHEMAS_AND_VALUES, agent_case, tool_case, with_readiness
from v11_full_scope.frameworks import canonical_implementation, native_implementation, run_framework_case
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily


PROFILE_CANDIDATES_MS = (5, 10, 20)
SELECTED_DEVELOPMENT_PERIOD_MS = 5
SCHEDULER_TOLERANCE_MS = 3


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    fields = list(row)
    if exists:
        with path.open("r", newline="", encoding="utf-8") as source:
            fields = next(csv.reader(source))
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def _trace(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value["raw_trace"]
    return value.evidence.get("raw_trace") or value.evidence["cover_trace"]


def _session_gate(trace: dict[str, Any], expected: int) -> dict[str, Any]:
    profile = load_v10_profile()
    events = trace["public_relay_events"]
    launches = trace["slot_launches"]
    client_ids = {event["relay_client_connection_id"] for event in events}
    gateway_ids = {event["relay_gateway_connection_id"] for event in events}
    request_sizes = {int(event["request_length"]) for event in events}
    response_sizes = {int(event["response_length"]) for event in events}
    setup = [event["stage"] for event in trace["public_setup_events"]]
    deadlines = [int(item["deadline_ns"]) for item in launches]
    constant_deadlines = all(
        deadlines[index] - deadlines[index - 1] == SELECTED_DEVELOPMENT_PERIOD_MS * 1_000_000
        for index in range(1, len(deadlines))
    )
    passed = all(
        (
            trace.get("session_status") == "COMPLETE",
            int(trace["admitted"]) == expected,
            len(trace["results"]) == expected,
            len(events) == profile.total_rounds,
            [int(event["round"]) for event in events] == list(range(1, profile.total_rounds + 1)),
            request_sizes == {profile.request_final_bytes},
            response_sizes == {profile.response_final_bytes},
            client_ids and len(client_ids) == 1,
            gateway_ids and len(gateway_ids) == 1,
            all(event.get("client_http_version") == "HTTP/2.0" for event in events),
            all(event.get("gateway_http_version") == "HTTP/2.0" for event in events),
            int(trace["schedule_misses"]) == 0,
            not trace["pending_operation_ids"],
            int(trace["silent_committed_result_losses"]) == 0,
            int(trace["dummy_provider_operations"]) == 0,
            int(trace["profile_overflow_events"]) == 0,
            len(launches) == profile.total_rounds,
            not any(bool(item["schedule_miss"]) for item in launches),
            constant_deadlines,
            setup.index("PUBLIC_SETUP_COMPLETE") < setup.index("T0_ASSIGNED"),
        )
    )
    slips = [int(item["launch_slip_ns"]) for item in launches]
    return {
        "passed": passed,
        "session_status": trace.get("session_status"),
        "admitted": trace["admitted"],
        "delivered": len(trace["results"]),
        "rounds": len(events),
        "client_connections": len(client_ids),
        "gateway_connections": len(gateway_ids),
        "http2": all(event.get("client_http_version") == "HTTP/2.0" and event.get("gateway_http_version") == "HTTP/2.0" for event in events),
        "schedule_misses": trace["schedule_misses"],
        "pending": len(trace["pending_operation_ids"]),
        "silent_committed_result_losses": trace["silent_committed_result_losses"],
        "dummy_heavy_ops": trace["dummy_provider_operations"],
        "profile_overflow": trace["profile_overflow_events"],
        "max_launch_slip_ns": max(slips, default=0),
        "p95_launch_slip_ns": sorted(slips)[max(0, int(0.95 * len(slips)) - 1)] if slips else 0,
        "constant_deadlines": constant_deadlines,
    }


def _overrides(period_ms: int = SELECTED_DEVELOPMENT_PERIOD_MS, **extra: object) -> dict[str, object]:
    return {
        "round_period_ms": period_ms,
        "scheduler_tolerance_ms": SCHEDULER_TOLERANCE_MS,
        **extra,
    }


def _case_for_gate(gate: str, index: int):
    suffix = f"v111-{gate.lower()}-{index:04d}"
    if gate == "EXTERNAL_HTTP":
        return replace(
            tool_case(suffix, "FRAMEWORK_NEUTRAL"),
            action_family=CanonicalActionFamily.EXTERNAL_HTTP,
            capability="external.local",
            logical_action_name="v11_external_http",
        )
    if gate == "DIRECT_AGENT_SERVICE":
        return agent_case(suffix, "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    if gate == "OPENAI_AGENT_AS_TOOL":
        return agent_case(suffix, "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL)
    if gate == "OPENAI_HANDOFF":
        return agent_case(suffix, "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF)
    if gate == "MICROSOFT_AGENT_AS_TOOL":
        return agent_case(suffix, "Microsoft Agent Framework", AgentServiceSubtype.AGENT_AS_TOOL)
    if gate == "TRUSTED_MODULE_LOCAL_AGENT":
        return agent_case(
            suffix,
            "FRAMEWORK_NEUTRAL",
            AgentServiceSubtype.DIRECT_AGENT_SERVICE,
            placement="TRUSTED_MODULE_LOCAL",
        )
    if gate == "STRUCTURED_MULTI_ARGUMENT_TOOL":
        return tool_case(suffix, "FRAMEWORK_NEUTRAL", schema_index=6)
    raise ValueError(gate)


def run_profile(root: Path, runner: Path) -> None:
    rows = root / "profile_selection.jsonl"
    # Candidate set is frozen here; the existing 5 ms profile is tested first.
    _write_json(root / "profile_candidates.json", {
        "periods_ms": PROFILE_CANDIDATES_MS,
        "rounds": 111,
        "request_bytes": 1079,
        "response_bytes": 800,
        "selection_rule": "smallest candidate with 20/20 COMPLETE sessions and zero schedule misses",
    })
    for index in range(20):
        output = root / "profile_raw" / f"p5-{index:03d}"
        if output.exists():
            continue
        case = replace(tool_case(f"profile-p5-{index}", "FRAMEWORK_NEUTRAL"), operation_id=f"opv111p5{index:04d}")
        try:
            value = canonical_external_outcome(case, output, runner_binary=runner, plan_overrides=_overrides())
            gate = _session_gate(_trace(value), 1)
            error = ""
        except Exception as exc:
            gate = {"passed": False}
            error = f"{type(exc).__name__}: {exc}"
        with rows.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"period_ms": 5, "iteration": index, **gate, "error": error}) + "\n")


def run_faults(root: Path, runner: Path) -> None:
    csv_path = root / "fault_injection.csv"
    delayed = replace(tool_case("v111-fault-delayed-stream", "FRAMEWORK_NEUTRAL"), operation_id="opv111faultdelay")
    try:
        value = canonical_external_outcome(
            delayed,
            root / "fault_raw" / "delayed-stream",
            runner_binary=runner,
            plan_overrides=_overrides(fault_delay_response_slot=1, fault_delay_response_ms=75),
        )
        trace = _trace(value)
        gate = _session_gate(trace, 1)
        later_launched_before_delayed_return = any(
            int(item["slot"]) > 1 and int(item.get("submit_ns", 0)) < 75_000_000
            for item in trace["slot_launches"]
        )
        _append_csv(csv_path, {
            "case": "DELAY_ONE_HTTP2_STREAM_75MS",
            **gate,
            "later_streams_launched": later_launched_before_delayed_return,
            "expected_failure": False,
            "error": "",
        })
    except Exception as exc:
        _append_csv(csv_path, {"case": "DELAY_ONE_HTTP2_STREAM_75MS", "passed": False, "expected_failure": False, "error": f"{type(exc).__name__}: {exc}"})

    stalled_output = root / "fault_raw" / "scheduler-stall"
    stalled = replace(tool_case("v111-fault-scheduler-stall", "FRAMEWORK_NEUTRAL"), operation_id="opv111faultstall")
    try:
        canonical_external_outcome(
            stalled,
            stalled_output,
            runner_binary=runner,
            plan_overrides=_overrides(fault_scheduler_stall_slot=2, fault_scheduler_stall_ms=30),
        )
        _append_csv(csv_path, {"case": "SCHEDULER_STALL_30MS", "passed": False, "expected_failure": True, "error": "unexpected COMPLETE"})
    except RuntimeError as exc:
        raw = json.loads((stalled_output / "canonical_session" / "go_canonical_result.json").read_text(encoding="utf-8"))
        _append_csv(csv_path, {
            "case": "SCHEDULER_STALL_30MS",
            "passed": raw["session_status"] == "SESSION_SCHEDULE_FAILURE" and int(raw["schedule_misses"]) > 0,
            "session_status": raw["session_status"],
            "schedule_misses": raw["schedule_misses"],
            "expected_failure": True,
            "error": str(exc),
        })


def run_stress(root: Path, runner: Path) -> None:
    csv_path = root / "reliability_stress.csv"

    def execute(gate: str, index: int, expected: int, function: Callable[[], Any]) -> None:
        try:
            value = function()
            trace = _trace(value)
            result = _session_gate(trace, expected)
            error = ""
        except Exception as exc:
            result = {"passed": False}
            error = f"{type(exc).__name__}: {exc}"
        _append_csv(csv_path, {"gate": gate, "iteration": index, **result, "error": error})

    for count, repetitions in ((1, 100), (10, 50), (50, 20)):
        for index in range(repetitions):
            output = root / "stress_raw" / f"tool-{count}" / f"{index:03d}"
            if output.exists():
                continue
            cases = [
                replace(tool_case(f"v111-tool-{count}-{index}-{step}", "FRAMEWORK_NEUTRAL"), operation_id=f"v111t{count:02d}{index:03d}{step:02d}")
                for step in range(count)
            ]
            execute(
                f"TOOL_{count}", index, count,
                lambda cases=cases, output=output: canonical_multi_action(cases, output, runner_binary=runner, plan_overrides=_overrides()),
            )

    single_gates = (
        "EXTERNAL_HTTP", "DIRECT_AGENT_SERVICE", "OPENAI_AGENT_AS_TOOL", "OPENAI_HANDOFF",
        "MICROSOFT_AGENT_AS_TOOL", "TRUSTED_MODULE_LOCAL_AGENT", "STRUCTURED_MULTI_ARGUMENT_TOOL",
    )
    for gate in single_gates:
        for index in range(20):
            output = root / "stress_raw" / gate.lower() / f"{index:03d}"
            if output.exists():
                continue
            case = _case_for_gate(gate, index)
            if gate in {"OPENAI_AGENT_AS_TOOL", "OPENAI_HANDOFF", "MICROSOFT_AGENT_AS_TOOL"}:
                def framework_run(case=case, output=output):
                    record = run_framework_case(case, canonical_implementation(output, runner_binary=runner, plan_overrides=_overrides()))
                    return record.runtime_evidence["action_implementation_evidence"]
                execute(gate, index, 1, framework_run)
            elif gate == "TRUSTED_MODULE_LOCAL_AGENT":
                execute(gate, index, 0, lambda case=case, output=output: canonical_internal_outcome(case, output, runner_binary=runner, plan_overrides=_overrides()))
            else:
                execute(gate, index, 1, lambda case=case, output=output: canonical_external_outcome(case, output, runner_binary=runner, plan_overrides=_overrides()))

    for gate in ("INTERNAL_VS_EXTERNAL_STRICT", "EARLY_VS_LATE_READY"):
        for index in range(20):
            pair_root = root / "stress_raw" / gate.lower() / f"{index:03d}"
            if pair_root.exists():
                continue
            try:
                if gate == "INTERNAL_VS_EXTERNAL_STRICT":
                    a = canonical_internal_outcome(
                        _case_for_gate("TRUSTED_MODULE_LOCAL_AGENT", index), pair_root / "A",
                        runner_binary=runner, plan_overrides=_overrides(),
                    )
                    b = canonical_external_outcome(
                        _case_for_gate("DIRECT_AGENT_SERVICE", index), pair_root / "B",
                        runner_binary=runner, plan_overrides=_overrides(),
                    )
                    expected_a, expected_b = 0, 1
                else:
                    a_case = with_readiness(tool_case(f"v111-early-{index}", "FRAMEWORK_NEUTRAL"), "EARLY_READY")
                    b_case = with_readiness(replace(tool_case(f"v111-late-{index}", "FRAMEWORK_NEUTRAL"), operation_id=f"opv111late{index:04d}"), "LATE_READY_WITHIN_BOUND")
                    a = canonical_external_outcome(a_case, pair_root / "A", runner_binary=runner, plan_overrides=_overrides())
                    b = canonical_external_outcome(b_case, pair_root / "B", runner_binary=runner, plan_overrides=_overrides())
                    expected_a = expected_b = 1
                ga, gb = _session_gate(_trace(a), expected_a), _session_gate(_trace(b), expected_b)
                pa, pb = public_projections(a), public_projections(b)
                passed = ga["passed"] and gb["passed"] and pa == pb
                _append_csv(csv_path, {
                    "gate": gate,
                    "iteration": index,
                    "passed": passed,
                    "session_status": "PAIR_COMPLETE" if passed else "PAIR_FAILURE",
                    "admitted": expected_a + expected_b,
                    "delivered": int(ga["delivered"]) + int(gb["delivered"]),
                    "rounds": int(ga["rounds"]) + int(gb["rounds"]),
                    "client_connections": int(ga["client_connections"]) + int(gb["client_connections"]),
                    "gateway_connections": int(ga["gateway_connections"]) + int(gb["gateway_connections"]),
                    "http2": ga["http2"] and gb["http2"],
                    "schedule_misses": int(ga["schedule_misses"]) + int(gb["schedule_misses"]),
                    "pending": int(ga["pending"]) + int(gb["pending"]),
                    "silent_committed_result_losses": int(ga["silent_committed_result_losses"]) + int(gb["silent_committed_result_losses"]),
                    "dummy_heavy_ops": int(ga["dummy_heavy_ops"]) + int(gb["dummy_heavy_ops"]),
                    "profile_overflow": int(ga["profile_overflow"]) + int(gb["profile_overflow"]),
                    "max_launch_slip_ns": max(int(ga["max_launch_slip_ns"]), int(gb["max_launch_slip_ns"])),
                    "p95_launch_slip_ns": max(int(ga["p95_launch_slip_ns"]), int(gb["p95_launch_slip_ns"])),
                    "constant_deadlines": ga["constant_deadlines"] and gb["constant_deadlines"],
                    "error": "",
                })
            except Exception as exc:
                _append_csv(csv_path, {"gate": gate, "iteration": index, "passed": False, "error": f"{type(exc).__name__}: {exc}"})


def semantic_cases() -> list[Any]:
    cases = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for schema_index in range(len(SCHEMAS_AND_VALUES)):
            cases.append(tool_case(f"v111-sem-{framework.split()[0].lower()}-{schema_index}", framework, schema_index))
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        cases.append(agent_case(f"v111-sem-{framework.split()[0].lower()}-aat", framework, AgentServiceSubtype.AGENT_AS_TOOL))
    cases.append(agent_case("v111-sem-openai-handoff", "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF))
    for effect in ("READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"):
        for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
            cases.append(tool_case(f"v111-sem-tool-{effect}-{scenario}", "OpenAI Agents SDK", 0, effect, scenario))
            cases.append(agent_case(f"v111-sem-agent-{effect}-{scenario}", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL, effect, scenario))
    base = tool_case("v111-sem-external", "OpenAI Agents SDK")
    for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
        cases.append(replace(base, case_id=f"v111-sem-external-{scenario}", operation_id=f"opv111ext{scenario.lower()}", action_family=CanonicalActionFamily.EXTERNAL_HTTP, capability="external.local", logical_action_name="v11_external_http", scenario=scenario))
    if len(cases) != 38:
        raise AssertionError(f"semantic regression must contain 38 cases, got {len(cases)}")
    return cases


def run_semantic(root: Path, runner: Path) -> None:
    csv_path = root / "semantic_regression.csv"
    for index, case in enumerate(semantic_cases()):
        output = root / "semantic_raw" / f"{index:03d}-{case.case_id}"
        if output.exists():
            continue
        try:
            native = run_framework_case(case, native_implementation)
            canonical = run_framework_case(case, canonical_implementation(output, runner_binary=runner, plan_overrides=_overrides()))
            evidence = canonical.runtime_evidence["action_implementation_evidence"]
            trace = _trace(evidence)
            gate = _session_gate(trace, 1)
            equal = native.projection() == canonical.projection()
            error = ""
        except Exception as exc:
            gate, equal = {"passed": False}, False
            error = f"{type(exc).__name__}: {exc}"
        _append_csv(csv_path, {"case_id": case.case_id, "framework": case.framework, "projection_equal": equal, **gate, "error": error})


def _composite_agent(case_id: str, subtype: AgentServiceSubtype):
    return replace(
        agent_case(case_id, "FRAMEWORK_NEUTRAL", subtype),
        agent_id=21,
        agent_capability="agent.workflow.21",
        capability="agent.workflow.21",
    )


def run_multi(root: Path, runner: Path) -> None:
    csv_path = root / "multi_action.csv"
    workflows = {
        "TOOL_TO_TOOL": [tool_case("v111-multi-tt-0", "FRAMEWORK_NEUTRAL"), replace(tool_case("v111-multi-tt-1", "FRAMEWORK_NEUTRAL", effect_semantics="IDEMPOTENT_EFFECT"), operation_id="opv111multitt1")],
        "TOOL_TO_AGENT_AS_TOOL": [tool_case("v111-multi-ta-0", "FRAMEWORK_NEUTRAL"), _composite_agent("v111-multi-ta-1", AgentServiceSubtype.AGENT_AS_TOOL)],
        "TOOL_TO_HANDOFF": [tool_case("v111-multi-th-0", "FRAMEWORK_NEUTRAL"), _composite_agent("v111-multi-th-1", AgentServiceSubtype.HANDOFF)],
        "AGENT_AS_TOOL_TO_TOOL": [_composite_agent("v111-multi-at-0", AgentServiceSubtype.AGENT_AS_TOOL), tool_case("v111-multi-at-1", "FRAMEWORK_NEUTRAL")],
        "OUT_OF_ORDER_READY": [with_readiness(tool_case("v111-multi-oo-0", "FRAMEWORK_NEUTRAL"), "LATE_READY_WITHIN_BOUND"), with_readiness(_composite_agent("v111-multi-oo-1", AgentServiceSubtype.AGENT_AS_TOOL), "EARLY_READY")],
    }
    for name, cases in workflows.items():
        output = root / "multi_raw" / name.lower()
        if output.exists():
            continue
        try:
            value = canonical_mixed_workflow(cases, output, runner_binary=runner, plan_overrides=_overrides())
            gate = _session_gate(value["raw_trace"], len(cases))
            passed = bool(value["functional"] and value["operation_id_association"] and gate["passed"])
            _append_csv(csv_path, {"workflow": name, "passed": passed, "operation_id_association": value["operation_id_association"], "delivered_order": "|".join(value["delivered_operation_ids"]), **gate, "error": ""})
        except Exception as exc:
            _append_csv(csv_path, {"workflow": name, "passed": False, "error": f"{type(exc).__name__}: {exc}"})


def run_host(root: Path, runner: Path) -> None:
    _write_json(root / "linux_host.json", {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "runner": str(runner),
        "runner_sha256_recorded_by_wrapper": True,
        "timing_privacy": "OPEN / NOT TESTED",
        "holdout_cases_executed": 0,
    })


def _projection(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(value, dict):
        return value["strict_structural_projection"], value["strict_size_projection"]
    return public_projections(value)


def _workflow_cases(prefix: str, capabilities: list[str]) -> list[Any]:
    values = []
    effects = {"tool.read": "READ_ONLY", "tool.idem": "IDEMPOTENT_EFFECT", "tool.nonidem": "NON_IDEMPOTENT_EFFECT"}
    for index, capability in enumerate(capabilities):
        value = replace(
            tool_case(f"{prefix}-{index}", "FRAMEWORK_NEUTRAL", effect_semantics=effects[capability]),
            operation_id=f"op{prefix.replace('-', '')}{index:02d}"[:32],
            agent_id=21,
            agent_capability="agent.workflow.21",
            capability=capability,
        )
        values.append(value)
    return values


def run_structural(root: Path, runner: Path) -> None:
    csv_path = root / "structural_regression.csv"

    def ext(case: Any, path: Path):
        return canonical_external_outcome(case, path, runner_binary=runner, plan_overrides=_overrides())

    def mixed(cases: list[Any], path: Path):
        return canonical_mixed_workflow(cases, path, runner_binary=runner, plan_overrides=_overrides())

    pairs: list[tuple[str, Callable[[Path], Any], int, Callable[[Path], Any], int]] = []
    pairs.append((
        "AGENT_IDENTITY",
        lambda path: ext(agent_case("v111-struct-agent-11", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE), path), 1,
        lambda path: ext(_composite_agent("v111-struct-agent-21", AgentServiceSubtype.DIRECT_AGENT_SERVICE), path), 1,
    ))
    tool_a = replace(
        tool_case("v111-struct-tool-a", "FRAMEWORK_NEUTRAL"),
        agent_id=1,
        agent_capability="agent.a",
        capability="tool.a",
    )
    pairs.append((
        "TOOL_ROUTE",
        lambda path: ext(tool_a, path), 1,
        lambda path: ext(tool_case("v111-struct-tool-read", "FRAMEWORK_NEUTRAL"), path), 1,
    ))
    external = replace(
        tool_case("v111-struct-external", "FRAMEWORK_NEUTRAL"),
        action_family=CanonicalActionFamily.EXTERNAL_HTTP,
        capability="external.local",
        logical_action_name="v11_external_http",
    )
    pairs.append((
        "ACTION_KIND",
        lambda path: ext(tool_case("v111-struct-kind-tool", "FRAMEWORK_NEUTRAL"), path), 1,
        lambda path: ext(external, path), 1,
    ))
    pairs.append((
        "ACTION_COUNT",
        lambda path: canonical_multi_action(_workflow_cases("v111-count-low", ["tool.read"]), path, runner_binary=runner, plan_overrides=_overrides()), 1,
        lambda path: mixed(_workflow_cases("v111-count-high", ["tool.read"] * 10), path), 10,
    ))
    pairs.append((
        "REPETITION",
        lambda path: mixed(_workflow_cases("v111-repeat", ["tool.read"] * 10), path), 10,
        lambda path: mixed(_workflow_cases("v111-varied", ["tool.read", "tool.idem"] * 5), path), 10,
    ))
    pairs.append((
        "FREQUENCY",
        lambda path: mixed(_workflow_cases("v111-freq-skew", ["tool.read"] * 9 + ["tool.idem"]), path), 10,
        lambda path: mixed(_workflow_cases("v111-freq-bal", ["tool.read", "tool.idem"] * 5), path), 10,
    ))
    pairs.append((
        "RARE_TARGET",
        lambda path: mixed(_workflow_cases("v111-rare-none", ["tool.read"] * 10), path), 10,
        lambda path: mixed(_workflow_cases("v111-rare-one", ["tool.read"] * 9 + ["tool.idem"]), path), 10,
    ))
    pairs.append((
        "TRANSITION_PATTERN",
        lambda path: mixed(_workflow_cases("v111-trans-ab", ["tool.read", "tool.idem"] * 5), path), 10,
        lambda path: mixed(_workflow_cases("v111-trans-ac", ["tool.read", "tool.nonidem"] * 5), path), 10,
    ))
    short = replace(tool_case("v111-struct-arg-short", "FRAMEWORK_NEUTRAL"), arguments={"city": "x"})
    long = replace(tool_case("v111-struct-arg-long", "FRAMEWORK_NEUTRAL"), arguments={"city": "x" * 128})
    pairs.append(("ARGUMENT_LENGTH", lambda path: ext(short, path), 1, lambda path: ext(long, path), 1))
    early = with_readiness(tool_case("v111-struct-early", "FRAMEWORK_NEUTRAL"), "EARLY_READY")
    late = with_readiness(tool_case("v111-struct-late", "FRAMEWORK_NEUTRAL"), "LATE_READY_WITHIN_BOUND")
    pairs.append(("COMPLETION_READINESS", lambda path: ext(early, path), 1, lambda path: ext(late, path), 1))
    internal = agent_case("v111-struct-internal", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE, placement="TRUSTED_MODULE_LOCAL")
    outside = agent_case("v111-struct-outside", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    pairs.append((
        "INTERNAL_VS_EXTERNAL",
        lambda path: canonical_internal_outcome(internal, path, runner_binary=runner, plan_overrides=_overrides()), 0,
        lambda path: ext(outside, path), 1,
    ))

    for index, (name, run_a, expected_a, run_b, expected_b) in enumerate(pairs):
        pair_root = root / "structural_raw" / f"{index:02d}-{name.lower()}"
        if pair_root.exists():
            continue
        try:
            a, b = run_a(pair_root / "A"), run_b(pair_root / "B")
            ga, gb = _session_gate(_trace(a), expected_a), _session_gate(_trace(b), expected_b)
            structural_a, size_a = _projection(a)
            structural_b, size_b = _projection(b)
            structural_equal = structural_a == structural_b
            size_equal = size_a == size_b
            passed = ga["passed"] and gb["passed"] and structural_equal and size_equal
            _append_csv(csv_path, {
                "pair": name,
                "passed": passed,
                "arm_a_functional": ga["passed"],
                "arm_b_functional": gb["passed"],
                "structural_equal": structural_equal,
                "size_equal": size_equal,
                "http2_both": ga["http2"] and gb["http2"],
                "schedule_misses": int(ga["schedule_misses"]) + int(gb["schedule_misses"]),
                "dummy_heavy_ops": int(ga["dummy_heavy_ops"]) + int(gb["dummy_heavy_ops"]),
                "profile_overflow": int(ga["profile_overflow"]) + int(gb["profile_overflow"]),
                "error": "",
            })
        except Exception as exc:
            _append_csv(csv_path, {"pair": name, "passed": False, "error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("profile", "fault", "stress", "semantic", "multi", "structural", "host", "all"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.runner.is_file():
        raise FileNotFoundError(args.runner)
    actions = {
        "profile": run_profile,
        "fault": run_faults,
        "stress": run_stress,
        "semantic": run_semantic,
        "multi": run_multi,
        "structural": run_structural,
        "host": run_host,
    }
    selected = tuple(actions) if args.mode == "all" else (args.mode,)
    for name in selected:
        actions[name](args.output, args.runner)


if __name__ == "__main__":
    main()
