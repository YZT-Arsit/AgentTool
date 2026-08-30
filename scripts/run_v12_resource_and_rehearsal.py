from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v11_3_profile_closure import execute_once, mixed_cases, strict_cases
from v11_4.profile import selected_profile
from v11_full_scope.frameworks import native_implementation
from v11_online.frameworks import run_online_framework_workflow
from v12_development.resources import snapshot


PROFILE = selected_profile(10, 3000)
PIR_RECORDS = 64


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.previous = "0" * 64
        self.count = 0

    def append(self, value: dict[str, Any]) -> None:
        body = {**value, "previous_record_sha256": self.previous}
        record = {**body, "record_sha256": canonical_sha(body)}
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
        self.previous = record["record_sha256"]
        self.count += 1


def _case(label: str, framework: str = "OpenAI Agents SDK"):
    return strict_cases(1, label, framework)[0]


def _canonical(output: Path, runner: Path, framework: str, workflow: str, cases) -> dict[str, Any]:
    return execute_once(
        output,
        runner,
        PROFILE,
        framework,
        workflow,
        list(cases),
        pir_record_count=PIR_RECORDS,
    )


def run_stress(output: Path, runner: Path, run_label: str = "") -> dict[str, Any]:
    root = output / ("resource_stress_500" + (f"_{run_label}" if run_label else ""))
    if root.exists():
        raise FileExistsError("decisive 500-unit resource stress is one-shot")
    root.mkdir(parents=True)
    preregistered = {
        "schema": "AgentTool.V12ResourceStressThresholds/1",
        "units": 500,
        "sample_every_units": 10,
        "final_fd_at_most_initial_plus": 8,
        "zombie_children": 0,
        "monotonic_fd_growth_final_100_allowed": False,
        "orphan_simplepir": 0,
        "orphan_canonical_runner": 0,
        "retry": False,
        "selected_holdout_cases": 0,
    }
    write_json(root / "preregistered_thresholds.json", preregistered)
    initial = snapshot()
    samples = [{"unit": 0, **initial}]
    failures: list[dict[str, Any]] = []
    for index in range(500):
        value = _canonical(
            root / "raw" / f"unit_{index + 1:03d}",
            runner,
            "OpenAI Agents SDK",
            "DYNAMIC_SEQUENCE",
            [_case(f"DEV-V12-STRESS-{index + 1:03d}")],
        )
        if not value.get("passed"):
            failures.append({"unit": index + 1, "error": value.get("error", "")})
        if (index + 1) % 10 == 0:
            row = {"unit": index + 1, **snapshot()}
            samples.append(row)
            print(
                f"V12_RESOURCE unit={index + 1}/500 fd={row['open_fd_count']} "
                f"children={row['live_child_processes']} failures={len(failures)}",
                flush=True,
            )
    final = snapshot()
    final_100 = [row["open_fd_count"] for row in samples if row["unit"] >= 400]
    monotonic_growth = all(a <= b for a, b in zip(final_100, final_100[1:])) and any(
        a < b for a, b in zip(final_100, final_100[1:])
    )
    passed = all(
        (
            not failures,
            final["open_fd_count"] <= initial["open_fd_count"] + 8,
            final["zombie_children"] == 0,
            not monotonic_growth,
            final["simplepir_processes"] == 0,
            final["canonical_runner_processes"] == 0,
        )
    )
    result = {
        "schema": "AgentTool.V12ResourceStressResult/1",
        "status": "PASS" if passed else "FAIL",
        "units_attempted": 500,
        "unit_failures": failures,
        "initial": initial,
        "final": final,
        "samples": samples,
        "final_100_fd_values": final_100,
        "monotonic_fd_growth_final_100": monotonic_growth,
        "selected_holdout_cases_executed": 0,
    }
    write_json(root / "result.json", result)
    return result


def _native(framework: str, workflow: str, cases) -> dict[str, Any]:
    return run_online_framework_workflow(framework, workflow, list(cases), native_implementation)


def _mutate_case(case, token: str):
    values = {}
    for index, field in enumerate(case.argument_schema.fields):
        values[field.name] = {
            "str": f"{token}-{index}",
            "int": 100 + index,
            "bool": index % 2 == 0,
            "optional_str": None,
        }[field.primitive_type]
    return replace(case, arguments=values)


def run_rehearsal(output: Path, runner: Path, rehearsal: int, run_label: str = "") -> dict[str, Any]:
    root = output / f"campaign_rehearsal_{rehearsal}{f'_{run_label}' if run_label else ''}"
    if root.exists():
        raise FileExistsError("full development rehearsal is one-shot")
    root.mkdir(parents=True)
    ledger = Ledger(root / "execution_ledger.jsonl")
    unit = 0
    semantic_pass = 0
    trajectory_pass = 0
    arm_values: dict[str, dict[str, Any]] = {}

    def record(family: str, role: str, target: str, status: str, started: int) -> None:
        nonlocal unit
        ledger.append(
            {
                "global_execution_index": unit,
                "unit_id": f"DEV-V12-R{rehearsal}-U{unit:03d}",
                "family": family,
                "role": role,
                "target_id": target,
                "status_class": status,
                "start_diagnostic_ns": started,
                "end_diagnostic_ns": time.time_ns(),
                "retry_allowed": False,
            }
        )

    for index in range(53):
        target = f"DEV-V12-R{rehearsal}-S-{index + 1:03d}"
        framework = "OpenAI Agents SDK" if index % 2 == 0 else "Microsoft Agent Framework"
        cases = [_case(target, framework)]
        unit += 1; started = time.time_ns()
        try:
            native = _native(framework, "DYNAMIC_SEQUENCE", cases)
            write_json(root / f"unit_{unit:03d}_native.json", native)
            native_status = "PASS"
        except Exception as exc:
            native = {}; native_status = f"NATIVE_REFERENCE_FAIL:{type(exc).__name__}:{exc}"
        record("SEMANTIC", "NATIVE", target, native_status, started)
        unit += 1; started = time.time_ns()
        canonical = _canonical(root / f"unit_{unit:03d}_canonical", runner, framework, "DYNAMIC_SEQUENCE", cases)
        equal = native.get("projection") == canonical.get("canonical_projection")
        status = "PASS" if canonical.get("passed") and equal else "CANONICAL_FUNCTIONAL_FAIL"
        semantic_pass += status == "PASS" and native_status == "PASS"
        record("SEMANTIC", "CANONICAL", target, status, started)

    families = (
        "TOOL_TO_TOOL",
        "TOOL_TO_AGENT_AS_TOOL",
        "AGENT_AS_TOOL_TO_TOOL",
        "TOOL_TO_HANDOFF",
        "INTERNAL_TO_EXTERNAL",
        "EXTERNAL_TO_INTERNAL",
    )
    for index in range(12):
        target = f"DEV-V12-R{rehearsal}-T-{index + 1:03d}"
        framework, workflow, cases = mixed_cases(families[index % len(families)], target)
        unit += 1; started = time.time_ns()
        try:
            native = _native(framework, workflow, cases)
            write_json(root / f"unit_{unit:03d}_native.json", native)
            native_status = "PASS"
        except Exception as exc:
            native = {}; native_status = f"NATIVE_REFERENCE_FAIL:{type(exc).__name__}:{exc}"
        record("TRAJECTORY", "NATIVE", target, native_status, started)
        unit += 1; started = time.time_ns()
        canonical = _canonical(root / f"unit_{unit:03d}_canonical", runner, framework, workflow, cases)
        equal = native.get("projection") == canonical.get("canonical_projection")
        status = "PASS" if canonical.get("passed") and equal else "CANONICAL_FUNCTIONAL_FAIL"
        trajectory_pass += status == "PASS" and native_status == "PASS"
        record("TRAJECTORY", "CANONICAL", target, status, started)

    for pair in range(14):
        for arm_name in ("A", "B"):
            target = f"DEV-V12-R{rehearsal}-P{pair + 1:02d}-{arm_name}"
            base = _case(target)
            case = _mutate_case(base, f"pair-{pair}-{arm_name}-{rehearsal}")
            unit += 1; started = time.time_ns()
            value = _canonical(root / f"unit_{unit:03d}_canonical", runner, "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [case])
            arm_values[target] = value
            record(
                f"STRUCTURAL_P{pair + 1:02d}",
                "STRUCTURAL_ARM",
                target,
                "PASS" if value.get("passed") else "CANONICAL_FUNCTIONAL_FAIL",
                started,
            )

    pair_pass = 0
    for pair in range(14):
        a = arm_values[f"DEV-V12-R{rehearsal}-P{pair + 1:02d}-A"]
        b = arm_values[f"DEV-V12-R{rehearsal}-P{pair + 1:02d}-B"]
        passed = bool(
            a.get("passed")
            and b.get("passed")
            and a.get("strict_structural_projection") == b.get("strict_structural_projection")
            and a.get("strict_size_projection") == b.get("strict_size_projection")
        )
        pair_pass += passed
        write_json(
            root / f"pair_{pair + 1:02d}_verdict.json",
            {"pair": pair + 1, "status": "PASS" if passed else "FAIL"},
        )
    rows = [json.loads(line) for line in (root / "execution_ledger.jsonl").read_text().splitlines()]
    final_resource = snapshot()
    passed = all(
        (
            unit == 158,
            ledger.count == 158,
            semantic_pass == 53,
            trajectory_pass == 12,
            pair_pass == 14,
            all(row["status_class"] == "PASS" for row in rows),
            final_resource["zombie_children"] == 0,
            final_resource["simplepir_processes"] == 0,
            final_resource["canonical_runner_processes"] == 0,
        )
    )
    summary = {
        "schema": "AgentTool.V12DevelopmentCampaignRehearsalSummary/1",
        "rehearsal": rehearsal,
        "status": "PASS" if passed else "FAIL",
        "ledger_records": ledger.count,
        "final_ledger_record_sha256": ledger.previous,
        "status_counts": dict(Counter(row["status_class"] for row in rows)),
        "semantic_pass": semantic_pass,
        "trajectory_pass": trajectory_pass,
        "structural_pair_pass": pair_pass,
        "resource": final_resource,
        "selected_holdout_cases_executed": 0,
    }
    write_json(root / "summary.json", summary)
    write_json(
        root / "campaign_completion.json",
        {
            "ledger_records": ledger.count,
            "final_ledger_record_sha256": ledger.previous,
            "summary_sha256": hashlib.sha256((root / "summary.json").read_bytes()).hexdigest(),
            "pair_verdicts": 14,
        },
    )
    return summary


def run_rehearsals(output: Path, runner: Path, run_label: str = "") -> dict[str, Any]:
    summaries = []
    for rehearsal in range(1, 6):
        value = run_rehearsal(output, runner, rehearsal, run_label)
        summaries.append(value)
        print(f"V12_REHEARSAL {rehearsal}/5 status={value['status']}", flush=True)
    result = {
        "schema": "AgentTool.V12FullCampaignRehearsalResults/1",
        "passed": sum(value["status"] == "PASS" for value in summaries),
        "total": 5,
        "summaries": summaries,
        "selected_holdout_cases_executed": 0,
    }
    write_json(output / ("full_campaign_rehearsal_results" + (f"_{run_label}" if run_label else "") + ".json"), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--phase", choices=("stress", "rehearsals", "all"), default="all")
    parser.add_argument("--run-label", default="")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase in {"stress", "all"}:
        run_stress(args.output, args.runner, args.run_label)
    if args.phase in {"rehearsals", "all"}:
        run_rehearsals(args.output, args.runner, args.run_label)


if __name__ == "__main__":
    main()
