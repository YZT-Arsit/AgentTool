from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_2_online_development import agent, tools
from scripts.run_v11_3_profile_closure import execute_once, strict_cases
from v11_4.profile import selected_profile
from v11_full_scope.fixtures import with_readiness
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import AgentServiceSubtype, V11ActionCase
from v11_online.frameworks import run_online_framework_workflow
from v11_online.session import OnlineSimplePIRResolver
from v12_development.baseline_views import BASELINES, DIMENSIONS


PROFILE = selected_profile(10, 3000)


def private_arms(dimension: str) -> tuple[list[V11ActionCase], list[V11ActionCase]]:
    label = f"DEV-V12-BASE-{dimension}"
    a = strict_cases(4, label + "-A")
    b = strict_cases(4, label + "-B")
    if dimension == "P1_AGENT_IDENTITY":
        b = [replace(case, agent_id=21, agent_capability="agent.workflow.21") for case in b]
    elif dimension == "P2_TOOL_ROUTE_IDENTITY":
        b = tools(label + "-B", "OpenAI Agents SDK", ["tool.idem"] * 4)
    elif dimension == "P3_ACTION_KIND":
        b = [agent(label + f"-B-{index}", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL) for index in range(4)]
    elif dimension == "P4_ACTUAL_ACTION_COUNT":
        a, b = strict_cases(3, label + "-A"), strict_cases(7, label + "-B")
    elif dimension == "P5_REPETITION":
        b = tools(label + "-B", "OpenAI Agents SDK", ["tool.read", "tool.idem"] * 2)
    elif dimension == "P6_FREQUENCY_SKEW":
        a = tools(label + "-A", "OpenAI Agents SDK", ["tool.read"] * 3 + ["tool.idem"])
        b = tools(label + "-B", "OpenAI Agents SDK", ["tool.read", "tool.idem"] * 2)
    elif dimension == "P7_RARE_TARGET":
        b = tools(label + "-B", "OpenAI Agents SDK", ["tool.read"] * 3 + ["tool.idem"])
    elif dimension == "P8_TRANSITION_ORDER":
        a = tools(label + "-A", "OpenAI Agents SDK", ["tool.read", "tool.idem"] * 2)
        b = tools(label + "-B", "OpenAI Agents SDK", ["tool.read"] * 2 + ["tool.idem"] * 2)
    elif dimension == "P9_PRIVATE_ARGUMENT_SIZE":
        b = [
            replace(
                case,
                arguments={
                    field.name: ("x" * 200 if field.primitive_type == "str" else case.arguments[field.name])
                    for field in case.argument_schema.fields
                },
            )
            for case in b
        ]
    elif dimension == "P10_PROVIDER_READINESS":
        a = [with_readiness(case, "EARLY_READY") for case in a]
        b = [with_readiness(case, "LATE_READY_WITHIN_BOUND") for case in b]
    elif dimension == "P11_INTERNAL_EXTERNAL":
        a = [agent(label + f"-A-{index}", "OpenAI Agents SDK", AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=False) for index in range(4)]
        b = [agent(label + f"-B-{index}", "OpenAI Agents SDK", AgentServiceSubtype.DIRECT_AGENT_SERVICE, internal=True) for index in range(4)]
    elif dimension == "P12_CAUSAL_DEPTH":
        a = [replace(case, continuation={"causal_parent": None}) for case in a]
        b = [replace(case, continuation={"causal_parent": None if index == 0 else b[index - 1].operation_id}) for index, case in enumerate(b)]
    elif dimension == "P13_AGENT_SERVICE_SUBTYPE":
        a = [agent(label + f"-A-{index}", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL) for index in range(4)]
        b = [agent(label + f"-B-{index}", "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF) for index in range(4)]
    elif dimension == "P14_DYNAMIC_PRIVATE_RESOLUTION":
        pass
    return a, b


def direct_view(cases: list[V11ActionCase], *, private_agent: bool) -> dict[str, Any]:
    value = {
        "endpoint_sequence": [case.capability for case in cases],
        "action_sequence": [case.action_family.value for case in cases],
        "subtype_sequence": [case.agent_service_subtype.value if case.agent_service_subtype else None for case in cases],
        "placement_sequence": [case.placement for case in cases],
        "continuation_sequence": [case.continuation for case in cases],
        "argument_size_sequence": [len(case.logical_arguments_json().encode()) for case in cases],
        "operation_count": len(cases),
    }
    if not private_agent:
        value["agent_id_sequence"] = [case.agent_id for case in cases]
    return value


def run_native(cases: list[V11ActionCase]) -> tuple[bool, list[int]]:
    value = run_online_framework_workflow("OpenAI Agents SDK", "DYNAMIC_SEQUENCE", cases, native_implementation)
    trajectory = value.get("projection", {}).get("trajectory", [])
    return (
        len(trajectory) == len(cases),
        [len(str(item.get("result", "")).encode()) for item in trajectory],
    )


def canonical(root: Path, runner: Path, cases: list[V11ActionCase], *, pir_delay_ms: int = 0) -> dict[str, Any]:
    return execute_once(
        root,
        runner,
        PROFILE,
        "OpenAI Agents SDK",
        "DYNAMIC_SEQUENCE",
        cases,
        pir_record_count=64,
        pir_delay_ms=pir_delay_ms,
    )


def compare(a: dict[str, Any], b: dict[str, Any], baseline: str, dimension: str, functional: bool) -> dict[str, Any]:
    request_a, request_b = a.get("request_sizes", []), b.get("request_sizes", [])
    response_a, response_b = a.get("response_sizes", []), b.get("response_sizes", [])
    return {
        "baseline": baseline,
        "dimension": dimension,
        "arm_a_functional": functional,
        "arm_b_functional": functional,
        "full_public_structural_projection_equal": a == b,
        "size_projection_equal": request_a == request_b and response_a == response_b,
        "request_count_equal": len(request_a) == len(request_b),
        "response_count_equal": len(response_a) == len(response_b),
        "scheduled_lifetime_equal": a.get("scheduled_lifetime") == b.get("scheduled_lifetime"),
        "endpoint_connection_view_equal": a.get("endpoint_connection_view") == b.get("endpoint_connection_view"),
        "evidence_class": "ACTUAL_DEV_EXECUTION_PUBLIC_PROJECTION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--go-bench", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("V12 baseline privacy development campaign is one-shot")
    args.output.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for baseline in BASELINES:
        resolver = None
        if baseline in {"B1_PIR_PLUS_DIRECT_ACTION", "B2_PIR_PLUS_OHTTP_UNSHAPED", "B3_PIR_PLUS_OHTTP_PADDED"}:
            resolver = OnlineSimplePIRResolver(args.output / f"{baseline.lower()}_pir", record_count=64)
            resolver.__enter__()
        try:
            for dimension in DIMENSIONS:
                cases_a, cases_b = private_arms(dimension)
                views: list[dict[str, Any]] = []
                functional = True
                for arm, cases in (("A", cases_a), ("B", cases_b)):
                    if baseline == "B0_DIRECT_NATIVE":
                        native_ok, result_sizes = run_native(cases)
                        functional &= native_ok
                        view = direct_view(cases, private_agent=False)
                        view.update(endpoint="DIRECT_NAMED", endpoint_connection_view={"named_endpoint_sequence":[case.capability for case in cases],"relay_connections":0,"gateway_connections":0}, request_sizes=[len(case.logical_arguments_json().encode()) for case in cases], response_sizes=result_sizes, scheduled_lifetime=len(cases))
                    elif baseline == "B1_PIR_PLUS_DIRECT_ACTION":
                        assert resolver is not None
                        for case in cases:
                            resolver.query(case.operation_id, case.agent_id)
                        native_ok, result_sizes = run_native(cases)
                        functional &= native_ok
                        view = direct_view(cases, private_agent=True)
                        view.update(endpoint="DIRECT_NAMED", endpoint_connection_view={"named_endpoint_sequence":[case.capability for case in cases],"relay_connections":0,"gateway_connections":0}, request_sizes=[len(case.logical_arguments_json().encode()) for case in cases], response_sizes=result_sizes, scheduled_lifetime=len(cases))
                    elif baseline in {"B2_PIR_PLUS_OHTTP_UNSHAPED", "B3_PIR_PLUS_OHTTP_PADDED"}:
                        assert resolver is not None
                        for case in cases:
                            resolver.query(case.operation_id, case.agent_id)
                        native_ok, result_sizes = run_native(cases)
                        functional &= native_ok
                        mode = "B2" if baseline.startswith("B2") else "B3"
                        argument_bytes = max(len(case.logical_arguments_json().encode()) for case in cases)
                        result_bytes = max(result_sizes)
                        result = json.loads(subprocess.check_output([str(args.go_bench), "--mode", mode, "--count", str(len(cases)), "--argument-bytes", str(argument_bytes), "--result-bytes", str(result_bytes)], text=True))
                        functional &= all((
                            int(result.get("relay_requests", -1)) == len(cases),
                            int(result.get("gateway_requests", -1)) == len(cases),
                            int(result.get("provider_invocations", -1)) == len(cases),
                            int(result.get("dummy_provider_operations", -1)) == 0,
                            int(result.get("relay_connections", 0)) >= 1,
                            int(result.get("gateway_connections", 0)) >= 1,
                            result.get("relay_exact_forwarding") is True,
                        ))
                        view = {
                            "endpoint": "OHTTP_RELAY",
                            "endpoint_connection_view": {
                                "relay_endpoint_class": result["relay_endpoint_class"],
                                "gateway_endpoint_class": result["gateway_endpoint_class"],
                                "relay_connections": int(result["relay_connections"]),
                                "gateway_connections": int(result["gateway_connections"]),
                            },
                            "request_sizes": [int(result["bytes_sent"]) // len(cases)] * len(cases),
                            "response_sizes": [int(result["bytes_received"]) // len(cases)] * len(cases),
                            "scheduled_lifetime": len(cases),
                        }
                    elif baseline == "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL" and dimension == "P11_INTERNAL_EXTERNAL" and arm == "B":
                        native_ok, result_sizes = run_native(cases)
                        functional &= native_ok
                        view = direct_view(cases, private_agent=True)
                        view.update(endpoint="INTERNAL_DIRECT", endpoint_connection_view={"endpoint":"INTERNAL_DIRECT","relay_connections":0,"gateway_connections":0}, request_sizes=[len(case.logical_arguments_json().encode()) for case in cases], response_sizes=result_sizes, scheduled_lifetime=len(cases))
                    else:
                        delay = 30 if dimension == "P14_DYNAMIC_PRIVATE_RESOLUTION" and arm == "B" else 0
                        value = canonical(args.output / "canonical_raw" / baseline / dimension / arm, args.runner, cases, pir_delay_ms=delay)
                        functional &= bool(value.get("passed"))
                        structural = value["strict_structural_projection"]
                        sizes = value["strict_size_projection"]
                        view = {
                            "endpoint": "STRICT_COMMON_RELAY" if baseline == "B5_FULL_STRICT" else "OHTTP_RELAY",
                            "endpoint_connection_view": {
                                "relay_endpoint_class": structural["relay_endpoint_class"],
                                "gateway_endpoint_class": structural["gateway_endpoint_class"],
                                "connection_count": structural["connection_count"],
                                "connection_reuse_pattern": structural["connection_reuse_pattern"],
                            },
                            "structural": structural,
                            "request_sizes": sizes["request_final_bytes"],
                            "response_sizes": sizes["response_final_bytes"],
                            "scheduled_lifetime": structural["scheduled_public_lifetime_ns"],
                        }
                    views.append(view)
                rows.append(compare(views[0], views[1], baseline, dimension, functional))
                print(f"V12_BASELINE {baseline} {dimension} functional={functional}", flush=True)
        finally:
            if resolver is not None:
                resolver.__exit__(None, None, None)
    with (args.output / "baseline_privacy_raw.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    status = "PASS" if len(rows) == 84 and all(row["arm_a_functional"] and row["arm_b_functional"] for row in rows) else "FAIL"
    (args.output / "result.json").write_text(json.dumps({"status": status, "rows": len(rows), "selected_v12_cases_executed": 0}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
