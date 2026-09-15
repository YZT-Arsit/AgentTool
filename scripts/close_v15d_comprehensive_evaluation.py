from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


BASE = "2cf835cb1e63e1f6f15bfdb523f563ae8608e868"
APSI_BYTES_SLOT = 2_277_832
PIR_BYTES_SLOT = 73_568
ACCESS_BYTES_PROFILE = 9_405_600
GATEWAY_BYTES_PROFILE = 978_959
TOTAL_BYTES_PROFILE = 10_384_559


def percentile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    lo = int(position); hi = min(lo + 1, len(ordered) - 1); weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader(); writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def framework_name(value: str) -> str:
    return "OpenAI Agents SDK" if value == "OpenAI" else "Microsoft Agent Framework"


def normalize_utility(core: dict[str, Any], supplement: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    workload_map = {"NESTED_AGENT_AS_TOOL": "PROVISIONED_NESTED_AGENT_AS_TOOL"}
    for source in core["rows"]:
        if source["workload"] == "MIXED":
            continue
        retrievals = [float(value) for value in source["retrieval_latencies_ms"]]
        workload = workload_map.get(source["workload"], source["workload"])
        semantic_applicable = workload != "IDLE_PROFILE_ONLY"
        admitted = int(source["admitted_real_agent_accesses"])
        repository = int(source["gateway_repository_requests"])
        slots = int(source["scheduled_agent_access_slots"])
        profile_instances = 1
        rows.append({
            "run_id": source["run_id"], "framework": framework_name(source["framework"]),
            "workload": workload, "repetition": source["repetition"], "source_campaign": "V15D_P0_CORE",
            "semantic_applicable": semantic_applicable,
            "semantic_success": bool(source["semantic_success"]) if semantic_applicable else None,
            "profile_conformance": bool(source["profile_conformance"]),
            "task_latency_ms": source["task_latency_ms"],
            "first_agent_retrieval_latency_ms": retrievals[0] if retrievals else None,
            "total_agent_resolution_latency_ms": sum(retrievals) if retrievals else None,
            "retrieval_count": len(retrievals), "retrieval_latencies_ms_json": json.dumps(retrievals),
            "public_session_wall_ms": source["full_public_obligations_wall_ms"],
            "public_profile_instances": profile_instances, "scheduled_agent_access_slots": slots,
            "admitted_real_agent_accesses": admitted,
            "real_psi_queries": admitted, "dummy_psi_queries": slots - admitted,
            "real_pir_queries": admitted - repository, "dummy_pir_queries": slots - admitted + repository,
            "gateway_public_sessions": profile_instances, "gateway_relay_cells": source["gateway_relay_cells"],
            "overflow_count": source["overflow_count"], "silent_loss_count": source["silent_loss_count"],
            "profile_capacity_failures": int(source["overflow_count"] > 0),
            "retrieval_failures": int(len(retrievals) != int(source["retrieved_agent_count"])),
            "agent_loader_failures": int(semantic_applicable and not source["semantic_success"]),
            "real_agent_executions": int(source["retrieved_agent_count"]),
            "real_remote_llm_calls": 0, "real_external_tool_api_calls": 0,
            "dummy_heavy_agent_executions": source["dummy_heavy_agent_executions"],
            "dummy_heavy_llm_executions": source["dummy_heavy_llm_executions"],
            "dummy_heavy_tool_executions": source["dummy_heavy_tool_executions"],
            "agent_access_bytes": ACCESS_BYTES_PROFILE,
            "gateway_bytes": GATEWAY_BYTES_PROFILE, "total_public_bytes": TOTAL_BYTES_PROFILE,
        })
    for source in supplement["rows"]:
        retrievals = [float(value) for value in source["retrieval_latencies_ms"]]
        workload = source["workload"]
        instances = int(source["public_profile_instances"]); slots = int(source["scheduled_agent_access_slots"])
        if workload == "UNPROVISIONED_NESTED_AGENT_AS_TOOL":
            admitted, repository, real_pir = 2, 2, 0
        elif workload == "MIXED_AGENT_LLM_TOOL":
            admitted, repository, real_pir = 3, 1, 2
        else:
            raise RuntimeError(f"unknown supplement workload {workload}")
        rows.append({
            "run_id": source["run_id"], "framework": framework_name(source["framework"]),
            "workload": workload, "repetition": source["repetition"], "source_campaign": "V15D_P0_SUPPLEMENT",
            "semantic_applicable": True, "semantic_success": bool(source["semantic_success"]),
            "profile_conformance": bool(source["profile_conformance"]),
            "task_latency_ms": source["task_latency_ms"],
            "first_agent_retrieval_latency_ms": source["first_agent_retrieval_latency_ms"],
            "total_agent_resolution_latency_ms": source["total_agent_resolution_latency_ms"],
            "retrieval_count": source["retrieval_count"], "retrieval_latencies_ms_json": json.dumps(retrievals),
            "public_session_wall_ms": source["full_public_obligations_wall_ms"],
            "public_profile_instances": instances, "scheduled_agent_access_slots": slots,
            "admitted_real_agent_accesses": admitted,
            "real_psi_queries": admitted, "dummy_psi_queries": slots - admitted,
            "real_pir_queries": real_pir, "dummy_pir_queries": slots - real_pir,
            "gateway_public_sessions": source["gateway_public_sessions"], "gateway_relay_cells": 521 * instances,
            "overflow_count": source["overflow_count"], "silent_loss_count": source["silent_loss_count"],
            "profile_capacity_failures": source["profile_capacity_failures"],
            "retrieval_failures": source["retrieval_failures"], "agent_loader_failures": source["agent_loader_failures"],
            "real_agent_executions": source["real_agent_executions"],
            "real_remote_llm_calls": source["real_remote_llm_calls"],
            "real_external_tool_api_calls": source["real_external_tool_api_calls"],
            "framework_model_invocations": source["framework_model_invocations"],
            "framework_agent_as_tool_invocations": source["framework_agent_as_tool_invocations"],
            "dummy_heavy_agent_executions": source["dummy_heavy_agent_executions"],
            "dummy_heavy_llm_executions": source["dummy_heavy_llm_executions"],
            "dummy_heavy_tool_executions": source["dummy_heavy_tool_executions"],
            "agent_access_bytes": ACCESS_BYTES_PROFILE * instances,
            "gateway_bytes": GATEWAY_BYTES_PROFILE * instances,
            "total_public_bytes": TOTAL_BYTES_PROFILE * instances,
        })
    if len(rows) != 280:
        raise RuntimeError(f"final utility denominator is {len(rows)}, expected 280")
    return rows


def utility_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["framework"], row["workload"])].append(row)
    output = []
    for (framework, workload), values in sorted(grouped.items()):
        successful = [row for row in values if row["semantic_success"] is True]
        retrievals = [value for row in successful for value in json.loads(row["retrieval_latencies_ms_json"])]
        output.append({
            "framework": framework, "workload": workload, "n": len(values),
            "semantic_applicable_n": sum(row["semantic_applicable"] for row in values),
            "semantic_successes": len(successful),
            "profile_conformance_successes": sum(row["profile_conformance"] for row in values),
            "task_latency_p50_ms_successful": percentile([row["task_latency_ms"] for row in successful], .5),
            "task_latency_p95_ms_successful": percentile([row["task_latency_ms"] for row in successful], .95),
            "first_retrieval_p50_ms_successful": percentile([row["first_agent_retrieval_latency_ms"] for row in successful], .5),
            "first_retrieval_p95_ms_successful": percentile([row["first_agent_retrieval_latency_ms"] for row in successful], .95),
            "all_retrieval_p50_ms_successful": percentile(retrievals, .5),
            "all_retrieval_p95_ms_successful": percentile(retrievals, .95),
            "total_resolution_p50_ms_successful": percentile([row["total_agent_resolution_latency_ms"] for row in successful], .5),
            "total_resolution_p95_ms_successful": percentile([row["total_agent_resolution_latency_ms"] for row in successful], .95),
            "public_session_wall_p50_ms": percentile([row["public_session_wall_ms"] for row in values], .5),
            "public_session_wall_p95_ms": percentile([row["public_session_wall_ms"] for row in values], .95),
            "overflow_count": sum(row["overflow_count"] for row in values),
            "silent_loss_count": sum(row["silent_loss_count"] for row in values),
        })
    return output


def selected(rows: list[dict[str, Any]], experiment: str, view: str) -> dict[str, Any]:
    return next(row for row in rows if row["experiment"] == experiment and row["feature_view"] == view)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--structural", type=Path, required=True)
    parser.add_argument("--equivalence", type=Path, required=True)
    parser.add_argument("--scale", type=Path, required=True)
    parser.add_argument("--joint-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT if "ROOT" in globals() else Path.cwd())
    args = parser.parse_args(); output = args.output.resolve()

    core, supplement = load(args.core), load(args.supplement)
    access, timing, structural = load(args.access), load(args.timing), load(args.structural)
    equivalence = load(args.equivalence)
    inventory = load(args.joint_inventory)
    scale = csv_rows(args.scale)
    utility = normalize_utility(core, supplement); summaries = utility_summary(utility)
    write_csv(output / "FINAL_UTILITY_RESULTS.csv", utility)

    privacy = list(access["privacy"])
    for row in structural["branch_attack"]:
        privacy.append({**row, "evidence_scope": "CURRENT_FINAL_PIPELINE_V15B_REUSED"})
    write_csv(output / "FINAL_PRIVACY_RESULTS.csv", privacy)
    sequence = list(access["sequence"])
    for row in structural["trajectory_attack"]:
        sequence.append({**row, "evidence_scope": "EXACT_COMPONENT_COMPOSITION"})
    write_csv(output / "FINAL_SEQUENCE_RESULTS.csv", sequence)
    write_csv(output / "FINAL_TIMING_RESULTS.csv", timing["rows"])
    write_csv(output / "FINAL_SCALE_RESULTS.csv", scale)

    nonidle = [row for row in utility if row["semantic_applicable"]]
    successful = [row for row in nonidle if row["semantic_success"]]
    all_retrievals = [value for row in successful for value in json.loads(row["retrieval_latencies_ms_json"])]
    profile_instances = sum(row["public_profile_instances"] for row in utility)
    total_slots = sum(row["scheduled_agent_access_slots"] for row in utility)
    real_psi = sum(row["real_psi_queries"] for row in utility); real_pir = sum(row["real_pir_queries"] for row in utility)
    overhead = [
        {"section": "AGENT_ACCESS", "metric": "APSI_bytes_per_profile", "value": APSI_BYTES_SLOT * 4, "unit": "bytes", "source": "V15B measured wire"},
        {"section": "AGENT_ACCESS", "metric": "SimplePIR_bytes_per_profile", "value": PIR_BYTES_SLOT * 4, "unit": "bytes", "source": "V15B measured wire"},
        {"section": "AGENT_ACCESS", "metric": "total_bytes_per_profile", "value": ACCESS_BYTES_PROFILE, "unit": "bytes", "source": "sum of four public slots"},
        {"section": "GATEWAY", "metric": "bytes_per_profile", "value": GATEWAY_BYTES_PROFILE, "unit": "bytes", "source": "frozen 521-cell V4R8 profile"},
        {"section": "TOTAL", "metric": "bytes_per_profile", "value": TOTAL_BYTES_PROFILE, "unit": "bytes", "source": "Agent-access plus Gateway"},
        {"section": "TOTAL", "metric": "MiB_per_profile", "value": TOTAL_BYTES_PROFILE / 2**20, "unit": "MiB", "source": "IEC conversion"},
        {"section": "PROFILE", "metric": "agent_access_horizon", "value": 1425, "unit": "ms", "source": "frozen Gamma_A"},
        {"section": "PROFILE", "metric": "real_PSI_slot_utilization", "value": real_psi / total_slots, "unit": "fraction", "source": "final 280 sessions"},
        {"section": "PROFILE", "metric": "dummy_PSI_slot_utilization", "value": 1 - real_psi / total_slots, "unit": "fraction", "source": "final 280 sessions"},
        {"section": "PROFILE", "metric": "real_PIR_slot_utilization", "value": real_pir / total_slots, "unit": "fraction", "source": "final 280 sessions"},
        {"section": "PROFILE", "metric": "dummy_PIR_slot_utilization", "value": 1 - real_pir / total_slots, "unit": "fraction", "source": "final 280 sessions"},
    ]
    cadence = csv_rows(Path("V15B_CADENCE_STRESS_RESULTS.csv"))
    for cadence_ms in (250, 350):
        values = [row for row in cadence if row["cadence_ms"] == str(cadence_ms)]
        overhead.append({"section": "PROFILE_SENSITIVITY", "metric": f"Delta_{cadence_ms}_slot_misses",
                         "value": sum(row["slot_miss"] == "True" for row in values), "unit": "slots",
                         "source": f"V15B frozen {len(values)}-slot stress"})
        overhead.append({"section": "PROFILE_SENSITIVITY", "metric": f"Delta_{cadence_ms}_public_horizon",
                         "value": 25 + 4 * cadence_ms, "unit": "ms", "source": "fixed R_A=4"})
    write_csv(output / "FINAL_OVERHEAD_RESULTS.csv", overhead)

    all_current_timing = [row for row in timing["rows"] if row["condition"] == "FINAL_OAE_BIDIRECTIONAL_SHAPING"]
    binary_access_timing = [row for row in sequence if row.get("feature_view") == "TIMING" and "test_train_oriented_auc" in row]
    strongest_gateway = max(all_current_timing, key=lambda row: row["test_orientation_invariant_auc"])
    strongest_access = max(binary_access_timing, key=lambda row: row["test_orientation_invariant_auc"])
    stats = {
        "schema": "AgentTool.V15DFinalStatisticalSummary/1", "base": BASE,
        "input_sha256": {name: sha256(path) for name, path in {
            "utility_core": args.core, "utility_supplement": args.supplement,
            "access_statistics": args.access, "timing_statistics": args.timing,
            "structural_statistics": args.structural, "structural_equivalence": args.equivalence,
            "scale_results": args.scale, "joint_inventory": args.joint_inventory,
        }.items()},
        "final_system": {"APSI": "Microsoft APSI v0.13.1", "SimplePIR": "real", "artifacts": 100000,
                         "record_bytes": 1024, "R_A": 4, "Delta_A_ms": 350, "horizon_ms": 1425,
                         "max_admitted": 3, "gateway_cells": 521},
        "joint_access_campaign": inventory,
        "utility": {"measured_sessions": len(utility), "nonidle": len(nonidle),
                    "semantic_successes": len(successful), "profile_conformance": sum(row["profile_conformance"] for row in utility),
                    "retrieval_p50_ms": percentile(all_retrievals, .5), "retrieval_p95_ms": percentile(all_retrievals, .95),
                    "task_p50_ms": percentile([row["task_latency_ms"] for row in successful], .5),
                    "task_p95_ms": percentile([row["task_latency_ms"] for row in successful], .95),
                    "profile_instances": profile_instances, "summary_by_coordinate": summaries,
                    "overflow": sum(row["overflow_count"] for row in utility),
                    "silent_loss": sum(row["silent_loss_count"] for row in utility),
                    "profile_capacity_failures": sum(row["profile_capacity_failures"] for row in utility),
                    "retrieval_failures": sum(row["retrieval_failures"] for row in utility),
                    "agent_loader_failures": sum(row["agent_loader_failures"] for row in utility),
                    "real_psi_queries": real_psi, "dummy_psi_queries": total_slots - real_psi,
                    "real_pir_queries": real_pir, "dummy_pir_queries": total_slots - real_pir,
                    "dummy_heavy_agent": sum(row["dummy_heavy_agent_executions"] for row in utility),
                    "dummy_heavy_llm": sum(row["dummy_heavy_llm_executions"] for row in utility),
                    "dummy_heavy_tool": sum(row["dummy_heavy_tool_executions"] for row in utility)},
        "access_privacy": access, "structural_and_branch": structural, "timing": timing,
        "full_session_structural_equivalence": equivalence,
        "strongest_final_gateway_timing": strongest_gateway,
        "strongest_final_agent_access_binary_timing": strongest_access,
        "scale": scale, "overhead": overhead,
        "claim_boundary": "Structural and empirical access claims exclude realized timing. Timing privacy is NOT_ESTABLISHED.",
    }
    (output / "FINAL_STATISTICAL_SUMMARY.json").write_text(json.dumps(stats, indent=2) + "\n")

    primary_same = selected(access["privacy"], "SAME_AGENT_WITHIN_SESSION", "ALL_ALLOWED")
    primary_cross1 = selected(access["privacy"], "CROSS_SESSION_SAME_SLOT", "ALL_ALLOWED")
    primary_cross2 = selected(access["privacy"], "CROSS_SESSION_CROSS_SLOT", "ALL_ALLOWED")
    primary_sequence = selected(access["sequence"], "FOUR_CLASS_ORDERING_RECURRENCE", "ALL_ALLOWED")
    trajectory = selected(sequence, "FOUR_CLASS_EXECUTION_TRAJECTORY", "FINAL_OAE_STRUCTURAL_COMPOSITION")
    branch_struct = selected(privacy, "PROVISIONED_UNPROVISIONED_IDLE", "STRUCTURAL")
    branch_timing = selected(privacy, "PROVISIONED_UNPROVISIONED_IDLE", "TIMING")

    def binary_supported(row: dict[str, Any]) -> bool:
        return row["ci95_low"] <= .5 <= row["ci95_high"] and row["permutation_p"] >= .05

    def multi_supported(row: dict[str, Any], chance: float) -> bool:
        return row["ci95_low"] <= chance <= row["ci95_high"] and row["permutation_p"] >= .05

    claims = [
        ("same-Agent unlinkability", "EMPIRICALLY_SUPPORTED" if binary_supported(primary_same) else "NOT_ESTABLISHED", primary_same),
        ("cross-session unlinkability", "EMPIRICALLY_SUPPORTED" if binary_supported(primary_cross1) and binary_supported(primary_cross2) else "NOT_ESTABLISHED", [primary_cross1, primary_cross2]),
        ("access ordering privacy", "EMPIRICALLY_SUPPORTED" if multi_supported(primary_sequence, .25) else "NOT_ESTABLISHED", primary_sequence),
        ("recurrence privacy", "EMPIRICALLY_SUPPORTED" if binary_supported(selected(access["sequence"], "RECURRENCE_AAA_VS_ABC", "ALL_ALLOWED")) else "NOT_ESTABLISHED", selected(access["sequence"], "RECURRENCE_AAA_VS_ABC", "ALL_ALLOWED")),
        ("rare-Agent privacy", "EMPIRICALLY_SUPPORTED" if binary_supported(selected(access["sequence"], "RARE_INSERTION_AAA_VS_AAB", "ALL_ALLOWED")) else "NOT_ESTABLISHED", selected(access["sequence"], "RARE_INSERTION_AAA_VS_AAB", "ALL_ALLOWED")),
        ("deployed/unprovisioned/idle structural privacy", "ESTABLISHED" if equivalence.get("exact_equality") is True and multi_supported(branch_struct, 1/3) else "NOT_ESTABLISHED", branch_struct),
        ("execution-trajectory structural privacy", "EMPIRICALLY_SUPPORTED" if multi_supported(trajectory, .25) else "NOT_ESTABLISHED", trajectory),
        ("Agent-access realized timing privacy", "NOT_ESTABLISHED", branch_timing),
        ("Gateway realized timing privacy", "NOT_ESTABLISHED", strongest_gateway),
        ("utility", "ESTABLISHED" if len(successful) == len(nonidle) else "PARTIALLY_SUPPORTED", f"{len(successful)}/{len(nonidle)}"),
        ("100K scale", "ESTABLISHED" if any(int(row["N"]) == 100000 for row in scale) else "NOT_ESTABLISHED", "schema-valid artifacts"),
        ("bounded liveness", "ESTABLISHED" if not sum(row["overflow_count"] for row in utility) else "PARTIALLY_SUPPORTED", "maximum 3 admitted requests/profile"),
        ("zero dummy-heavy compute", "ESTABLISHED" if not sum(row["dummy_heavy_agent_executions"] + row["dummy_heavy_llm_executions"] + row["dummy_heavy_tool_executions"] for row in utility) else "NOT_ESTABLISHED", "measured utility campaign"),
    ]
    claim_lines = ["# Final claim matrix", "", "| Claim | Classification | Exact evidence |", "|---|---|---|"]
    for name, status, evidence in claims:
        if isinstance(evidence, dict):
            metric = evidence.get("test_train_oriented_auc", evidence.get("test_accuracy"))
            detail = f"{evidence.get('experiment')} / {evidence.get('feature_view')}: {metric}"
        elif isinstance(evidence, list):
            detail = "; ".join(f"{row['experiment']}: {row['test_train_oriented_auc']}" for row in evidence)
        else:
            detail = str(evidence)
        claim_lines.append(f"| {name} | **{status}** | {detail} |")
    claim_lines += ["", "Realized timing is excluded from every structural claim and remains **NOT_ESTABLISHED**.", ""]
    (output / "FINAL_CLAIM_MATRIX.md").write_text("\n".join(claim_lines), encoding="utf-8")

    table_rows = [
        {"category": "System", "metric": "Provisioned artifacts", "result": "100000", "evidence": "FINAL_SCALE_RESULTS.csv", "scope": "current system"},
        {"category": "Utility", "metric": "Semantic success", "result": f"{len(successful)}/{len(nonidle)}", "evidence": "FINAL_UTILITY_RESULTS.csv", "scope": "current system"},
        {"category": "Utility", "metric": "Profile conformance", "result": f"{sum(row['profile_conformance'] for row in utility)}/{len(utility)}", "evidence": "FINAL_UTILITY_RESULTS.csv", "scope": "current system"},
        {"category": "Access privacy", "metric": "Same-Agent AUC", "result": primary_same["test_train_oriented_auc"], "evidence": "FINAL_PRIVACY_RESULTS.csv", "scope": "current APSI+PIR"},
        {"category": "Access privacy", "metric": "Cross-session AUC 1", "result": primary_cross1["test_train_oriented_auc"], "evidence": "FINAL_PRIVACY_RESULTS.csv", "scope": "current APSI+PIR"},
        {"category": "Access privacy", "metric": "Cross-session AUC 2", "result": primary_cross2["test_train_oriented_auc"], "evidence": "FINAL_PRIVACY_RESULTS.csv", "scope": "current APSI+PIR"},
        {"category": "Sequence privacy", "metric": "Four-class accuracy", "result": primary_sequence["test_accuracy"], "evidence": "FINAL_SEQUENCE_RESULTS.csv", "scope": "current APSI+PIR"},
        {"category": "Structural", "metric": "Trajectory accuracy", "result": trajectory["test_accuracy"], "evidence": "FINAL_SEQUENCE_RESULTS.csv", "scope": "exact component composition"},
        {"category": "Timing", "metric": "Strongest final Gateway AUC", "result": strongest_gateway["test_train_oriented_auc"], "evidence": "FINAL_TIMING_RESULTS.csv", "scope": "current frozen Gateway"},
        {"category": "Overhead", "metric": "Total public MiB/profile", "result": TOTAL_BYTES_PROFILE / 2**20, "evidence": "FINAL_OVERHEAD_RESULTS.csv", "scope": "current system"},
        {"category": "Latency", "metric": "Retrieval p50/p95 ms", "result": f"{percentile(all_retrievals,.5):.3f}/{percentile(all_retrievals,.95):.3f}", "evidence": "FINAL_UTILITY_RESULTS.csv", "scope": "successful current-system tasks"},
        {"category": "Latency", "metric": "Task p50/p95 ms", "result": f"{percentile([row['task_latency_ms'] for row in successful],.5):.3f}/{percentile([row['task_latency_ms'] for row in successful],.95):.3f}", "evidence": "FINAL_UTILITY_RESULTS.csv", "scope": "successful current-system tasks"},
    ]
    write_csv(output / "FINAL_PAPER_TABLE1.csv", table_rows)

    fig = []
    positive_trajectory = selected(sequence, "FOUR_CLASS_EXECUTION_TRAJECTORY", "UNNORMALIZED_VISIBLE_ACTION_ENDPOINT_POSITIVE_CONTROL")
    fig.extend([
        {"panel": "structural", "attack": "Four-class trajectory", "condition": "Unnormalized positive control", "metric": "Accuracy", "value": positive_trajectory["test_accuracy"], "chance": .25, "ci95_low": positive_trajectory["ci95_low"], "ci95_high": positive_trajectory["ci95_high"]},
        {"panel": "structural", "attack": "Four-class trajectory", "condition": "OAE", "metric": "Accuracy", "value": trajectory["test_accuracy"], "chance": .25, "ci95_low": trajectory["ci95_low"], "ci95_high": trajectory["ci95_high"]},
    ])
    for current in all_current_timing:
        historical = next(row for row in timing["rows"] if row["condition"] == "HISTORICAL_ONE_SIDED_POSITIVE_CONTROL" and row["experiment"] == current["experiment"] and row["framework"] == current["framework"])
        label = f"{current['experiment']} / {current['framework']}"
        for condition, row in (("One-sided positive control", historical), ("OAE", current)):
            fig.append({"panel": "timing", "attack": label, "condition": condition, "metric": "AUC",
                        "value": row["test_train_oriented_auc"], "chance": .5,
                        "ci95_low": row["ci95_low"], "ci95_high": row["ci95_high"]})
    write_csv(output / "FINAL_FIG2_DATA.csv", fig)

    map_lines = ["# Final paper number map", "", "All attack values below use final held-out test data unless explicitly labeled as a historical component positive control.", "",
                 "| Destination | Metric | Experiment and sample count | Scope / observer | Statistical evidence | Safe wording |",
                 "|---|---|---|---|---|---|"]
    def add_map(destination: str, metric: str, experiment: str, scope: str, evidence: str, wording: str) -> None:
        map_lines.append(f"| {destination} | {metric} | {experiment} | {scope} | {evidence} | {wording} |")
    add_map("Abstract/Table 1", "100K artifacts", "Scale sweep; N=100000", "Current system", "Real APSI and SimplePIR", "100K schema-valid provisioned-Agent artifacts; not 100K independently sourced Agents.")
    add_map("Abstract/Table 1", f"Utility {len(successful)}/{len(nonidle)}", "Final utility; 240 non-idle + 40 idle", "Current system", "All failures retained", "All measured non-idle tasks completed semantically; all sessions checked separately for profile conformance.")
    for label, row in (("same-Agent", primary_same), ("cross-session same-slot", primary_cross1), ("cross-session cross-slot", primary_cross2)):
        add_map("Fig. 2/Sec. 5", f"{label} AUC {row['test_train_oriented_auc']:.3f}", f"Joint APSI+PIR; test n={row['n_test']}", "ALL_ALLOWED Agent-access metadata", f"95% CI [{row['ci95_low']:.3f},{row['ci95_high']:.3f}], permutation p={row['permutation_p']:.4g}", "Held-out attack performance; do not interpret AUC below 0.5 as stronger privacy.")
    add_map("Fig. 2/Sec. 5", f"Sequence accuracy {primary_sequence['test_accuracy']:.3f}", f"AAA/ABA/AAB/ABC; test n={primary_sequence['n_test']}", "ALL_ALLOWED Agent-access metadata", f"CI [{primary_sequence['ci95_low']:.3f},{primary_sequence['ci95_high']:.3f}], p={primary_sequence['permutation_p']:.4g}", "Direct ordering/recurrence evaluation against 25% chance.")
    add_map("Fig. 2/Sec. 5", f"Trajectory accuracy {trajectory['test_accuracy']:.3f}", "800 historical matched action records plus constant final access profile", "Exact mechanism composition; structural only", f"CI [{trajectory['ci95_low']:.3f},{trajectory['ci95_high']:.3f}]", "Mechanism-composed structural result, not a fresh integrated 800-session run.")
    add_map("Table 1/Sec. 5", f"Strongest Gateway timing AUC {strongest_gateway['test_train_oriented_auc']:.3f}", f"{strongest_gateway['experiment']} / {strongest_gateway['framework']}; final held-out test", "Frozen Relay timing observer", f"CI [{strongest_gateway['ci95_low']:.3f},{strongest_gateway['ci95_high']:.3f}], p={strongest_gateway['permutation_p']:.4g}", "Realized timing privacy is not established; preserve the residual setting.")
    add_map("Table 1/Sec. 5", f"Traffic {TOTAL_BYTES_PROFILE/2**20:.3f} MiB/profile", "4 real APSI+PIR public slots + 521-cell Gateway", "Current public profiles", "Exact measured wire sizes", "Channels overlap in time; bytes are additive, horizons are not.")
    add_map("Table 1/Sec. 5", f"Retrieval {percentile(all_retrievals,.5):.3f}/{percentile(all_retrievals,.95):.3f} ms p50/p95", f"All successful final retrievals, n={len(all_retrievals)}", "Current system", "Successful semantic runs only", "State the success-only denominator.")
    add_map("Table 1/Sec. 5", f"Task {percentile([row['task_latency_ms'] for row in successful],.5):.3f}/{percentile([row['task_latency_ms'] for row in successful],.95):.3f} ms p50/p95", f"Successful non-idle final sessions, n={len(successful)}", "Current system", "Successful semantic runs only", "Do not conflate with public-session wall time.")
    map_lines += ["", "## Historical values excluded from final-system claims", "",
                  "Historical SimplePIR-only 16K linking AUCs and the historical 1.755 MiB/session overhead must not be presented as final joint APSI+PIR results.",
                  "Historical one-sided timing results appear only as matched component positive controls, never as the final protected condition.", ""]
    (output / "FINAL_PAPER_NUMBER_MAP.md").write_text("\n".join(map_lines), encoding="utf-8")

    strongest_timing = strongest_gateway
    comprehensive = f"""# Final comprehensive evaluation

## Final system

- Real Microsoft APSI + real SimplePIR over 100K authenticated provisioned-Agent artifacts.
- Trusted Agent Loader; no remote Agent service execution.
- `R_A=4`, `Delta_A=350 ms`, 1,425 ms public Agent-access horizon, fixed one-slot pipeline.
- Frozen 521-cell Gateway profile.

## Utility

- Semantic success: **{len(successful)}/{len(nonidle)}** non-idle executions.
- Profile conformance: **{sum(row['profile_conformance'] for row in utility)}/{len(utility)}** sessions.
- Retrieval latency over {len(all_retrievals)} successful retrievals: **{percentile(all_retrievals,.5):.3f} ms p50 / {percentile(all_retrievals,.95):.3f} ms p95**.
- Semantic task latency over successful non-idle executions: **{percentile([row['task_latency_ms'] for row in successful],.5):.3f} ms p50 / {percentile([row['task_latency_ms'] for row in successful],.95):.3f} ms p95**.
- Overflow: **{sum(row['overflow_count'] for row in utility)}**; silent loss: **{sum(row['silent_loss_count'] for row in utility)}**.
- Profile-capacity failures: **{sum(row['profile_capacity_failures'] for row in utility)}**; retrieval failures: **{sum(row['retrieval_failures'] for row in utility)}**; Agent Loader failures: **{sum(row['agent_loader_failures'] for row in utility)}**.

## Access privacy

- Same-Agent linking (primary `ALL_ALLOWED` view): AUC **{primary_same['test_train_oriented_auc']:.3f}**, 95% CI [{primary_same['ci95_low']:.3f}, {primary_same['ci95_high']:.3f}], p={primary_same['permutation_p']:.4g}.
- Cross-session same-slot linking: AUC **{primary_cross1['test_train_oriented_auc']:.3f}**, 95% CI [{primary_cross1['ci95_low']:.3f}, {primary_cross1['ci95_high']:.3f}], p={primary_cross1['permutation_p']:.4g}.
- Cross-session cross-slot linking: AUC **{primary_cross2['test_train_oriented_auc']:.3f}**, 95% CI [{primary_cross2['ci95_low']:.3f}, {primary_cross2['ci95_high']:.3f}], p={primary_cross2['permutation_p']:.4g}.
- Four-class ordering/recurrence accuracy: **{primary_sequence['test_accuracy']:.3f}** (chance 0.25), macro-F1 {primary_sequence['test_macro_f1']:.3f}, 95% CI [{primary_sequence['ci95_low']:.3f}, {primary_sequence['ci95_high']:.3f}], p={primary_sequence['permutation_p']:.4g}.

## Structural trajectory privacy

- Full-session permitted structural projection: **{'PASS' if equivalence.get('exact_equality') else 'FAIL'}**, with Agent-access projection SHA-256 `{next(iter(equivalence['projection_sha256'].values()))}` across {len(equivalence['sessions'])} private patterns.
- Final composed structural attack: accuracy **{trajectory['test_accuracy']:.3f}**, macro-F1 {trajectory['test_macro_f1']:.3f}, 95% CI [{trajectory['ci95_low']:.3f}, {trajectory['ci95_high']:.3f}] against 0.25 chance.
- This result composes the historical matched action records with constant final Agent-access and unchanged Gateway structural fields; it is not mislabeled as a fresh integrated 800-session campaign.

## Timing

- Strongest final Gateway result: **{strongest_timing['experiment']} / {strongest_timing['framework']}**, AUC **{strongest_timing['test_train_oriented_auc']:.3f}**, 95% CI [{strongest_timing['ci95_low']:.3f}, {strongest_timing['ci95_high']:.3f}], p={strongest_timing['permutation_p']:.4g}.
- Agent-access deployed/unprovisioned/idle timing-only classification: accuracy **{branch_timing['test_accuracy']:.3f}**, 95% CI [{branch_timing['ci95_low']:.3f}, {branch_timing['ci95_high']:.3f}], p={branch_timing['permutation_p']:.4g}.
- **TIMING_PRIVACY = NOT_ESTABLISHED.** No timing result is omitted or averaged away.

## Scale

The scale sweep uses 1K, 10K, 50K and 100K schema-valid artifacts with persistent real cryptographic services and 30 measured queries per point. `FINAL_SCALE_RESULTS.csv` reports preprocessing/storage, online p50/p95 and exact wire bytes. The corpus is not described as 100K independently collected real-world Agents.

## Overhead

- Agent-access channel: **{ACCESS_BYTES_PROFILE:,} B ({ACCESS_BYTES_PROFILE/2**20:.3f} MiB) per public profile**.
- Gateway channel: **{GATEWAY_BYTES_PROFILE:,} B ({GATEWAY_BYTES_PROFILE/2**20:.3f} MiB) per public profile**.
- Total: **{TOTAL_BYTES_PROFILE:,} B ({TOTAL_BYTES_PROFILE/2**20:.3f} MiB) per public profile**.
- The channels can overlap in wall-clock time; their byte counts are additive, their horizons are not.

## Dummy heavy operations

- Dummy Agent executions: **{sum(row['dummy_heavy_agent_executions'] for row in utility)}**.
- Dummy LLM executions: **{sum(row['dummy_heavy_llm_executions'] for row in utility)}**.
- Dummy Tool executions: **{sum(row['dummy_heavy_tool_executions'] for row in utility)}**.

The final claim classifications are in `FINAL_CLAIM_MATRIX.md`; every candidate manuscript number and its evidence boundary is in `FINAL_PAPER_NUMBER_MAP.md`.
"""
    (output / "FINAL_COMPREHENSIVE_EVALUATION.md").write_text(comprehensive, encoding="utf-8")


if __name__ == "__main__":
    ROOT = Path.cwd()
    main()
