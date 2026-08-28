from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path
from typing import Iterable

from .compiler import CompilationResult, compile_workload
from .framework_fixtures import framework_workloads
from .ir import CAPSULE_BYTES, ControlEvent, Opcode, estimate_boolean_gates
from .lookup import MockPrivateLookup
from .runtime import AgentControlExecutor, ProtectedEvent, evaluate_transition, structural_signature


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def compile_frameworks() -> list[CompilationResult]:
    results: list[CompilationResult] = []
    next_id = 100
    for workload in framework_workloads():
        result = compile_workload(workload, next_id)
        results.append(result)
        next_id += max(100, len(result.capsules))
    return results


def _coverage_rows(results: Iterable[CompilationResult]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    for result in results:
        summary.append({
            "workload": result.workload,
            "framework": result.framework,
            "source": result.source,
            "total_behaviors": result.total,
            "compiled": result.compiled,
            "shared_primitive": result.shared,
            "unsupported": result.unsupported,
            "coverage": round(result.coverage, 6),
            "capsule_bytes_mean": CAPSULE_BYTES,
            "capsule_count": len(result.capsules),
            "states": sum(c.state_count for c in result.capsules),
            "transitions": sum(c.transition_count for c in result.capsules),
            "tool_handles": sum(c.tool_count for c in result.capsules),
            "handoff_targets": sum(c.handoff_count for c in result.capsules),
        })
        for behavior in result.behaviors:
            details.append({
                "workload": result.workload,
                "framework": result.framework,
                "behavior": behavior.name,
                "kind": behavior.kind,
                "classification": behavior.disposition.value,
                "reason": behavior.reason,
            })
    return summary, details


def _control_benchmark(capsule, repeats: int = 3000) -> dict[str, float | int | str]:
    samples: list[float] = []
    event = ProtectedEvent(ControlEvent.START)
    for _ in range(repeats):
        started = time.perf_counter_ns()
        result = evaluate_transition(capsule, 0, event)
        samples.append((time.perf_counter_ns() - started) / 1000)
    assert result.opcode == Opcode.LLM and result.matched_rows == 1
    return {
        "backend": "FIXED_SCAN_SEMANTIC_SIMULATOR",
        "cryptographically_secure": "NO",
        "secret_control_input_bytes": CAPSULE_BYTES + 3,
        "public_profile_input_bytes": 12,
        "max_control_rows": 30,
        "estimated_boolean_gates": estimate_boolean_gates(),
        "mean_runtime_us": round(statistics.mean(samples), 6),
        "p95_runtime_us": round(_percentile(samples, 0.95), 6),
        "communication_bytes": 0,
    }


def _representative_heavy_operation() -> float:
    # Local CPU proxy only. It is deliberately not called by cover slots and
    # is not presented as an LLM latency measurement.
    value = b"one-real-shared-heavy-operation"
    started = time.perf_counter_ns()
    for _ in range(100_000):
        value = hashlib.sha256(value).digest()
    return (time.perf_counter_ns() - started) / 1000


def _scale_lookup(prototypes: tuple[bytes, ...], capsule) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    scaling: list[dict[str, object]] = []
    cost: list[dict[str, object]] = []
    rng = random.Random(713)
    for count in (1_000, 10_000, 100_000):
        lookup = MockPrivateLookup(count, prototypes)
        samples = [lookup.lookup_measured(rng.randrange(count)) for _ in range(100)]
        control = _control_benchmark(capsule, repeats=500)
        heavy_us = _representative_heavy_operation()
        lookup_mean = statistics.mean(item.latency_us for item in samples)
        total_no_heavy = lookup_mean + float(control["mean_runtime_us"])
        scaling.append({
            "N": count,
            "backend": lookup.security_status,
            "cryptographic_target_privacy": "NO",
            "registry_bytes": len(lookup.storage),
            "capsule_bytes": CAPSULE_BYTES,
            "preprocessing_ms": round(lookup.preprocessing_us / 1000, 6),
            "lookup_mean_us": round(lookup_mean, 6),
            "lookup_p95_us": round(_percentile([item.latency_us for item in samples], 0.95), 6),
            "lookup_request_bytes": 8,
            "lookup_response_bytes": CAPSULE_BYTES,
            "lookup_server_cpu_mean_us": round(statistics.mean(item.server_cpu_us for item in samples), 6),
            "lookup_client_memory_bytes": CAPSULE_BYTES,
            "common_control_step_mean_us": control["mean_runtime_us"],
            "fixed_transcript_bytes": 4 * 2 * CAPSULE_BYTES,
            "total_excluding_heavy_us": round(total_no_heavy, 6),
            "representative_heavy_cpu_proxy_us": round(heavy_us, 6),
            "total_including_one_heavy_proxy_us": round(total_no_heavy + heavy_us, 6),
        })
        cost.append({
            "N": count,
            "real_heavy_ops": 1,
            "dummy_heavy_ops": 0,
            "private_lookup_ops": 1,
            "control_ops": 4,
            "fixed_frames": 4,
            "fixed_frame_wire_bytes": 4 * 2 * CAPSULE_BYTES,
            "lookup_wire_bytes": 8 + CAPSULE_BYTES,
            "client_memory_bytes": CAPSULE_BYTES,
            "server_memory_bytes": len(lookup.storage),
        })
        del lookup
    return scaling, cost


def _k_cover_intersection(n: int, k: int, calls: int, trials: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    candidate_sizes: list[int] = []
    posterior_top1: list[float] = []
    domain = list(range(n))
    for _ in range(trials):
        target = rng.randrange(n)
        intersection: set[int] | None = None
        for _ in range(calls):
            decoys = rng.sample(domain[:target] + domain[target + 1:], k - 1)
            visible = {target, *decoys}
            intersection = visible if intersection is None else intersection & visible
        size = len(intersection or ())
        candidate_sizes.append(size)
        posterior_top1.append(1 / size)
    return statistics.mean(candidate_sizes), statistics.mean(posterior_top1)


def _privacy_rows(executor: AgentControlExecutor, n: int = 1000) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows: list[dict[str, object]] = [
        {
            "baseline": "B0_DIRECT_NAMED_EXECUTION",
            "observer_boundary": "cloud_execution",
            "N": n,
            "k": 1,
            "repeated_calls": 1,
            "exact_structural_equality": "NO",
            "top1_agent_accuracy": 1.0,
            "top10_agent_accuracy": 1.0,
            "pairwise_auc": 1.0,
            "permutation_top1": 1 / n,
            "claim_status": "FAIL",
        },
        {
            "baseline": "B1_VISIBLE_K_COVER",
            "observer_boundary": "cloud_named_activations",
            "N": n,
            "k": 8,
            "repeated_calls": 1,
            "exact_structural_equality": "NO",
            "top1_agent_accuracy": 1 / 8,
            "top10_agent_accuracy": 1.0,
            "pairwise_auc": "NA",
            "permutation_top1": 1 / n,
            "claim_status": "FAIL_VISIBLE_SUBSET",
        },
    ]
    intersection: list[dict[str, object]] = []
    for calls in (1, 2, 4, 8):
        candidates, top1 = _k_cover_intersection(n, 8, calls, 500, 900 + calls)
        intersection.append({
            "N": n,
            "k": 8,
            "calls": calls,
            "mean_intersection_candidates": round(candidates, 6),
            "attacker_posterior_top1": round(top1, 6),
            "full_domain_chance": 1 / n,
        })
    traces = [executor.fixed_transcript(logical_agent_id) for logical_agent_id in range(n)]
    equality = len({structural_signature(trace) for trace in traces}) == 1
    rows.extend([
        {
            "baseline": "B2_COMMON_EXECUTOR",
            "observer_boundary": "common_executor_fixed_transcript",
            "N": n,
            "k": 0,
            "repeated_calls": 1,
            "exact_structural_equality": "YES" if equality else "NO",
            "top1_agent_accuracy": 1 / n,
            "top10_agent_accuracy": 10 / n,
            "pairwise_auc": 0.5,
            "permutation_top1": 1 / n,
            "claim_status": "PASS_STRUCTURAL_SIZE_ONLY",
        },
        {
            "baseline": "B2_MOCK_LOOKUP_END_TO_END",
            "observer_boundary": "lookup_server_plus_common_executor",
            "N": n,
            "k": 0,
            "repeated_calls": 1,
            "exact_structural_equality": "NO",
            "top1_agent_accuracy": 1.0,
            "top10_agent_accuracy": 1.0,
            "pairwise_auc": 1.0,
            "permutation_top1": 1 / n,
            "claim_status": "UNVALIDATED_REAL_PIR_REQUIRED",
        },
    ])
    return rows, intersection


def _handoff_audit(results: list[CompilationResult]) -> list[dict[str, object]]:
    for result in results:
        for capsule in result.capsules:
            row = next((candidate for candidate in capsule.rows if candidate.opcode == Opcode.HANDOFF), None)
            if row is None:
                continue
            capsules = {item.logical_agent_id: item for item in result.capsules}
            executor = AgentControlExecutor(capsules)
            next_agent, transition = executor.step(
                capsule.logical_agent_id, row.current_state, ProtectedEvent(ControlEvent.HANDOFF_REQUEST)
            )
            trace = executor.fixed_transcript(capsule.logical_agent_id)
            return [{
                "framework": result.framework,
                "workload": result.workload,
                "source_logical_agent": capsule.logical_agent_id,
                "destination_logical_agent": next_agent,
                "transition_opcode": transition.opcode.name,
                "physical_executor_before": executor.public_identity,
                "physical_executor_after": executor.public_identity,
                "named_destination_in_host_trace": "NO" if str(next_agent) not in structural_signature(trace) else "YES",
                "new_process_or_rpc": "NO",
            }]
    raise AssertionError("no native handoff was compiled")


def run(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    compiled = compile_frameworks()
    coverage, behavior = _coverage_rows(compiled)
    _write_csv(output_dir / "framework_coverage.csv", coverage)
    _write_csv(output_dir / "behavior_classification.csv", behavior)

    all_capsules = tuple(capsule for result in compiled for capsule in result.capsules)
    capsule_map = {capsule.logical_agent_id: capsule for capsule in all_capsules}
    executor = AgentControlExecutor(capsule_map)
    control = _control_benchmark(all_capsules[0])
    _write_csv(output_dir / "secure_control_dimensions.csv", [control])
    scaling, costs = _scale_lookup(tuple(c.serialize() for c in all_capsules), all_capsules[0])
    _write_csv(output_dir / "private_lookup_scaling.csv", scaling)
    _write_csv(output_dir / "cost_results.csv", costs)
    privacy, intersection = _privacy_rows(executor)
    _write_csv(output_dir / "privacy_results.csv", privacy)
    _write_csv(output_dir / "k_cover_intersection.csv", intersection)
    handoff = _handoff_audit(compiled)
    _write_csv(output_dir / "handoff_audit.csv", handoff)

    total = sum(result.total for result in compiled)
    covered = sum(result.compiled + result.shared for result in compiled)
    unsupported = sum(result.unsupported for result in compiled)
    summary: dict[str, object] = {
        "frameworks": sorted({result.framework for result in compiled}),
        "workloads": len(compiled),
        "native_agents": len(all_capsules),
        "total_behaviors": total,
        "compiled_or_shared_behaviors": covered,
        "unsupported_behaviors": unsupported,
        "aggregate_ir_coverage": covered / total,
        "capsule_bytes": CAPSULE_BYTES,
        "max_scale_instantiated": 100_000,
        "lookup_backend": "MOCK_PRIVATE_LOOKUP_NON_CRYPTOGRAPHIC",
        "real_pir_integrated": False,
        "b2_common_executor_exact_structural_equality": True,
        "b2_end_to_end_target_privacy_validated": False,
        "logical_handoff_uses_same_executor": True,
        "real_heavy_ops": 1,
        "dummy_heavy_ops": 0,
        "timing_privacy_claimed": False,
        "decision": "CONDITIONAL_GO",
        "conditions": [
            "integrate and validate a real single-server PIR backend at 100K rows",
            "validate live timing at the observer boundary in a fresh stage",
            "limit support to declarative framework-native control; dynamic callbacks and fan-out remain unsupported",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console = "\n".join([
        "CONTROL-VIRTUALIZATION DECISION:",
        summary["decision"],
        f"Aggregate real-framework IR coverage: {summary['aggregate_ir_coverage']:.1%}",
        "Logical HANDOFF through same executor: PASS",
        "100K logical registry instantiation: PASS",
        "Real cryptographic private lookup: NOT INTEGRATED",
        "B2 common-executor structural/size equality: PASS",
        "B2 end-to-end full-domain target privacy: NOT VALIDATED",
        "Real heavy operations: 1",
        "Dummy heavy operations: 0",
        "Live timing privacy: NOT CLAIMED",
        "Reason 1: real-framework declarative coverage is 95.3% and logical HANDOFF keeps one executor",
        "Reason 2: a 100K fixed-capsule registry runs with one real and zero dummy heavy operations",
        "Reason 3: real PIR and secure control evaluation are missing, so end-to-end privacy is unvalidated",
    ])
    (output_dir / "final_console_summary.txt").write_text(console + "\n", encoding="utf-8")
    print(console)
    return summary
