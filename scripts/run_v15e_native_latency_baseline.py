from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.fixtures import functional_artifacts
from v14_provisioned_agents.loader import AgentLoader, LoadedFrameworkAgent
from v14_provisioned_agents.models import ProvisionedAgentArtifactV1


WORKLOADS = (
    "PROVISIONED_ORDINARY",
    "UNPROVISIONED_ORDINARY",
    "NESTED_AGENT_AS_TOOL",
    "REPEATED_AGENT",
    "MIXED_AGENT_LLM_TOOL",
)
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def execute_workload(
    framework: str,
    workload: str,
    artifacts: dict[int, ProvisionedAgentArtifactV1],
) -> tuple[list[str], list[str], int, int, int]:
    base = 101 if framework == "OpenAI Agents SDK" else 201

    def load(agent_id: int, children: tuple[LoadedFrameworkAgent, ...] = ()) -> LoadedFrameworkAgent:
        return AgentLoader().load(artifacts[agent_id], children)

    observed: list[str] = []
    expected: list[str] = []
    agent_executions = 0
    model_invocations = 0
    agent_as_tool_invocations = 0

    if workload == "PROVISIONED_ORDINARY":
        agent = load(base)
        observed.append(agent.run())
        expected.append(artifacts[base].runtime_policy["expected_output"])
        agent_executions, model_invocations = 1, 1
    elif workload == "UNPROVISIONED_ORDINARY":
        agent_id = 1_000_000 + base
        agent = load(agent_id)
        observed.append(agent.run())
        expected.append(artifacts[agent_id].runtime_policy["expected_output"])
        agent_executions, model_invocations = 1, 1
    elif workload == "NESTED_AGENT_AS_TOOL":
        parent_id, child_id = base + 1, base + 2
        parent = load(parent_id, (load(child_id),))
        observed.append(parent.run())
        expected.append(artifacts[parent_id].runtime_policy["expected_output"])
        agent_executions, model_invocations, agent_as_tool_invocations = 2, 3, 1
    elif workload == "REPEATED_AGENT":
        for _ in range(3):
            agent = load(base)
            observed.append(agent.run())
            expected.append(artifacts[base].runtime_policy["expected_output"])
        agent_executions, model_invocations = 3, 3
    elif workload == "MIXED_AGENT_LLM_TOOL":
        parent_id, child_id, ordinary_id = base + 1, base + 2, 1_000_000 + base
        parent = load(parent_id, (load(child_id),))
        ordinary = load(ordinary_id)
        observed.extend((parent.run(), ordinary.run()))
        expected.extend(
            (
                artifacts[parent_id].runtime_policy["expected_output"],
                artifacts[ordinary_id].runtime_policy["expected_output"],
            )
        )
        agent_executions, model_invocations, agent_as_tool_invocations = 3, 4, 1
    else:
        raise ValueError(f"unknown workload: {workload}")

    return observed, expected, agent_executions, model_invocations, agent_as_tool_invocations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    args = parser.parse_args()
    if not 5 <= args.repetitions <= 10:
        raise ValueError("final native baseline requires 5--10 measured repetitions")
    if not 0 <= args.warmups <= 2:
        raise ValueError("at most two warmups are permitted")

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    artifacts = {artifact.canonical_agent_id: artifact for artifact in functional_artifacts()}

    # Warm each framework/workload coordinate without recording a measured value.
    for framework in FRAMEWORKS:
        for workload in WORKLOADS:
            for _ in range(args.warmups):
                observed, expected, *_ = execute_workload(framework, workload, artifacts)
                if observed != expected:
                    raise RuntimeError(f"warmup semantic failure: {framework}/{workload}")

    rows: list[dict[str, Any]] = []
    run_number = 0
    for repetition in range(1, args.repetitions + 1):
        # Reverse each adjacent repetition to reduce monotonic host-order bias.
        coordinates = [(framework, workload) for framework in FRAMEWORKS for workload in WORKLOADS]
        if repetition % 2 == 0:
            coordinates.reverse()
        for execution_order, (framework, workload) in enumerate(coordinates, start=1):
            run_number += 1
            started_ns = time.monotonic_ns()
            failure_category = ""
            semantic_success = False
            observed: list[str] = []
            expected: list[str] = []
            agent_executions = model_invocations = agent_as_tool_invocations = 0
            try:
                (
                    observed,
                    expected,
                    agent_executions,
                    model_invocations,
                    agent_as_tool_invocations,
                ) = execute_workload(framework, workload, artifacts)
                semantic_success = observed == expected
                if not semantic_success:
                    failure_category = "SEMANTIC_MISMATCH"
            except Exception as exc:  # The failed measured observation remains in the denominator.
                failure_category = f"{type(exc).__name__}:{exc}"
            completed_ns = time.monotonic_ns()
            rows.append(
                {
                    "run_id": f"V15E-NATIVE-{run_number:03d}",
                    "framework": framework,
                    "workload": workload,
                    "configuration": "NATIVE",
                    "repetition": repetition,
                    "execution_order": execution_order,
                    "start_monotonic_ns": started_ns,
                    "semantic_completion_monotonic_ns": completed_ns,
                    "task_latency_ms": (completed_ns - started_ns) / 1e6,
                    "semantic_success": semantic_success,
                    "failure_category": failure_category,
                    "expected_result_count": len(expected),
                    "observed_result_count": len(observed),
                    "real_agent_executions": agent_executions,
                    "framework_model_invocations": model_invocations,
                    "framework_agent_as_tool_invocations": agent_as_tool_invocations,
                    "apsi_operations": 0,
                    "simplepir_operations": 0,
                    "gateway_public_sessions": 0,
                    "cover_schedule_slots": 0,
                    "retry_count": 0,
                }
            )
            print(f"{rows[-1]['run_id']} {framework} {workload} success={semantic_success}", flush=True)

    raw_fields = list(rows[0])
    raw_path = output / "FINAL_NATIVE_LATENCY_RUNS.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=raw_fields)
        writer.writeheader()
        writer.writerows(rows)

    summary_rows: list[dict[str, Any]] = []
    for framework in FRAMEWORKS:
        for workload in WORKLOADS:
            selected = [row for row in rows if row["framework"] == framework and row["workload"] == workload]
            successful = [float(row["task_latency_ms"]) for row in selected if row["semantic_success"]]
            summary_rows.append(
                {
                    "framework": framework,
                    "workload": workload,
                    "configuration": "NATIVE",
                    "measured_executions": len(selected),
                    "successes": len(successful),
                    "failures": len(selected) - len(successful),
                    "task_latency_p50_ms": percentile(successful, 0.50) if successful else "",
                    "task_latency_p95_ms": percentile(successful, 0.95) if successful else "",
                    "task_latency_mean_ms": statistics.mean(successful) if successful else "",
                    "task_latency_stdev_ms": statistics.stdev(successful) if len(successful) > 1 else "",
                    "retries": 0,
                    "scope": "CURRENT_FINAL_WORKLOAD_NATIVE_SEMANTIC_BASELINE",
                }
            )
    summary_path = output / "FINAL_NATIVE_LATENCY_RESULTS.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    if len(rows) != len(FRAMEWORKS) * len(WORKLOADS) * args.repetitions:
        raise RuntimeError("native baseline denominator mismatch")
    if not all(row["semantic_success"] for row in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
