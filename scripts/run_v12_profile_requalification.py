from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_3_profile_closure import execute_once, mixed_cases, strict_cases, structural_specs, summary_row
from scripts.run_v11_4_profile_qualification import MIXED_FAMILIES, mixed_spec
from v11_4.profile import selected_profile
from v11_full_scope.frameworks import native_implementation, run_framework_case


PROFILE = selected_profile(10, 3000)
PIR_RECORDS = 64


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def execute(
    output: Path,
    runner: Path,
    framework: str,
    workflow: str,
    cases,
    *,
    native: bool = False,
    require_strict_causal: bool = True,
):
    return execute_once(
        output, runner, PROFILE, framework, workflow, list(cases),
        compare_native=native,
        pir_record_count=PIR_RECORDS,
        require_strict_causal=require_strict_causal,
    )


def capability_preflight(root: Path, runner: Path) -> dict[str, Any]:
    case_oa = strict_cases(1, "DEV-V12-PREFLIGHT-OPENAI")[0]
    case_ms = strict_cases(1, "DEV-V12-PREFLIGHT-MICROSOFT", "Microsoft Agent Framework")[0]
    openai = run_framework_case(case_oa, native_implementation)
    microsoft = run_framework_case(case_ms, native_implementation)
    canonical = execute(root / "canonical_tool_ohttp", runner, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [case_oa])
    checks = {
        "tiny_simplepir_query": bool(canonical.get("dynamic_pir")),
        "canonical_ordinary_tool": bool(canonical.get("passed")),
        "ohttp_relay_gateway": bool(canonical.get("trace_gate", {}).get("checks", {}).get("fixed_ohttp_suite")),
        "openai_native_action": bool(openai.projection()),
        "microsoft_native_action": bool(microsoft.projection()),
    }
    result = {
        "schema": "AgentTool.V12CapabilityPreflight/1",
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "selected_v12_cases_executed": 0,
    }
    write_json(root / "capability_preflight.json", result)
    return result


def final_reliability(root: Path, runner: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for count, repetitions in {10: 100, 20: 50, 30: 50, 50: 50}.items():
        for iteration in range(repetitions):
            value = execute(root / f"causal_{count}" / f"{iteration:03d}", runner, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(count, f"DEV-V12-REL-C{count}-{iteration:03d}"))
            rows.append(summary_row(f"CAUSAL_{count}", iteration, value))
        print(f"V12_REQUAL causal_{count} complete", flush=True)
    for kind in ("TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL", "TOOL_TO_HANDOFF", "MICROSOFT_TOOL_TO_AGENT_AS_TOOL"):
        for iteration in range(25):
            framework, workflow, cases = mixed_spec(kind, f"DEV-V12-REL-{kind}-{iteration:03d}")
            value = execute(root / "mixed" / kind.lower() / f"{iteration:03d}", runner, framework, workflow, cases)
            rows.append(summary_row("MIXED_AGENT_TRAJECTORY", iteration, value, family=kind))
    for kind in ("INTERNAL_TO_EXTERNAL", "EXTERNAL_TO_INTERNAL"):
        for iteration in range(25):
            framework, workflow, cases = mixed_spec(kind, f"DEV-V12-REL-{kind}-{iteration:03d}")
            value = execute(root / "internal_external" / kind.lower() / f"{iteration:03d}", runner, framework, workflow, cases)
            rows.append(summary_row("INTERNAL_EXTERNAL_MIXED", iteration, value, family=kind))
    for iteration in range(50):
        framework, workflow, cases = mixed_spec("STRUCTURED_TOOL_TO_AGENT_AS_TOOL", f"DEV-V12-REL-STRUCT-{iteration:03d}")
        value = execute(root / "structured" / f"{iteration:03d}", runner, framework, workflow, cases)
        rows.append(summary_row("STRUCTURED_MULTI_ARGUMENT", iteration, value))
    return rows


def mixed_qualification(root: Path, runner: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in MIXED_FAMILIES:
        for iteration in range(30):
            framework, workflow, cases = mixed_spec(kind, f"DEV-V12-MIX-{kind}-{iteration:03d}")
            value = execute(root / kind.lower() / f"{iteration:03d}", runner, framework, workflow, cases)
            rows.append(summary_row(kind, iteration, value))
        print(f"V12_REQUAL mixed_{kind} complete", flush=True)
    return rows


def regressions(root: Path, runner: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semantic: list[dict[str, Any]] = []
    for index, kind in enumerate((*MIXED_FAMILIES, "STRICT_CAUSAL_10", "MICROSOFT_CAUSAL_3")):
        if kind == "STRICT_CAUSAL_10":
            framework, workflow, cases = "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", strict_cases(10, "DEV-V12-SEM-OA10")
        elif kind == "MICROSOFT_CAUSAL_3":
            framework, workflow, cases = "Microsoft Agent Framework", "DYNAMIC_SEQUENCE", strict_cases(3, "DEV-V12-SEM-MS3", "Microsoft Agent Framework")
        else:
            framework, workflow, cases = mixed_spec(kind, f"DEV-V12-SEM-{kind}")
        value = execute(root / "semantic" / kind.lower(), runner, framework, workflow, cases, native=True)
        semantic.append(summary_row(kind, index, value))
    structural: list[dict[str, Any]] = []
    for name, (workflow_a, cases_a), (workflow_b, cases_b) in structural_specs():
        a = execute(
            root / "structural" / name.lower() / "A",
            runner,
            "OpenAI Agents SDK",
            workflow_a,
            cases_a,
            require_strict_causal=workflow_a == "DYNAMIC_SEQUENCE",
        )
        b = execute(
            root / "structural" / name.lower() / "B",
            runner,
            "OpenAI Agents SDK",
            workflow_b,
            cases_b,
            require_strict_causal=workflow_b == "DYNAMIC_SEQUENCE",
        )
        structural.append({
            "pair": name,
            "arm_a_functional": bool(a.get("passed")),
            "arm_b_functional": bool(b.get("passed")),
            "structural_equal": a.get("strict_structural_projection") == b.get("strict_structural_projection"),
            "size_equal": a.get("strict_size_projection") == b.get("strict_size_projection"),
        })
        structural[-1]["passed"] = all(structural[-1][key] for key in ("arm_a_functional", "arm_b_functional", "structural_equal", "size_equal"))
    return semantic, structural


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    if root.exists():
        raise FileExistsError("V12 decisive profile requalification is one-shot")
    root.mkdir(parents=True)
    capability = capability_preflight(root / "capability", args.runner)
    reliability = final_reliability(root / "final_reliability_raw", args.runner)
    mixed = mixed_qualification(root / "mixed_raw", args.runner)
    semantic, structural = regressions(root / "regression_raw", args.runner)
    write_csv(root / "final_reliability.csv", reliability)
    write_csv(root / "mixed_causal_families.csv", mixed)
    write_csv(root / "semantic_regression.csv", semantic)
    write_csv(root / "structural_regression.csv", structural)
    counters = {
        key: sum(int(row.get(key, 0) or 0) for row in reliability + mixed + semantic)
        for key in ("dummy_heavy_ops", "profile_overflow", "schedule_misses", "silent_committed_result_loss")
    }
    gates = {
        "capability_preflight": capability["status"] == "PASS",
        "final_reliability_450_of_450": len(reliability) == 450 and all(row["passed"] for row in reliability),
        "mixed_causal_240_of_240": len(mixed) == 240 and all(row["passed"] for row in mixed),
        "causal_depths_10_20_30_50": all(any(row["group"] == f"CAUSAL_{depth}" and row["passed"] for row in reliability) for depth in (10, 20, 30, 50)),
        "semantic_regression_at_least_10": len(semantic) >= 10 and all(row["passed"] for row in semantic),
        "structural_regression_at_least_12": len(structural) >= 12 and all(row["passed"] for row in structural),
        "zero_safety_counters": all(value == 0 for value in counters.values()),
    }
    write_json(root / "result.json", {
        "schema": "AgentTool.V12ProfileRequalification/1",
        "profile": PROFILE.public_schema(),
        "pir_development_record_count": PIR_RECORDS,
        "gates": gates,
        "counters": counters,
        "status": "PASS" if all(gates.values()) else "FAIL",
        "selected_v12_cases_executed": 0,
    })


if __name__ == "__main__":
    main()
