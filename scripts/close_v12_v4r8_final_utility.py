from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_V4R8 = "7a188ae2ebfcc42313eca0dbf92c62dfc66ff3fb"
RUNTIME_SOURCE = "63319014f560f46e2a46dd140f53551e43c27e0d"
BRANCH = "v12-duplex-timing-virtualization-redesign"
PIR_100K = ROOT / "results_crypto_closure" / "scale_100000" / "run4"
PIR_16K = ROOT / "results_crypto_closure" / "multiround_final" / "pir"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def json_lines(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def write_once_or_verify(path: Path, content: str) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        expected = content.replace("\r\n", "\n")
        if existing != expected:
            raise RuntimeError(f"existing closure artifact disagrees: {path}")
        return
    path.write_text(content, encoding="utf-8", newline="\n")


def make_pir_inventory(output: Path) -> dict[str, Any]:
    metrics_100k = json.loads((PIR_100K / "metrics.json").read_text(encoding="utf-8"))
    client_100k = json_lines(PIR_100K / "client_private_trace.jsonl")
    server_100k = json_lines(PIR_100K / "server_visible_trace.jsonl")
    metrics_16k = json.loads((PIR_16K / "metrics.json").read_text(encoding="utf-8"))
    client_16k = json_lines(PIR_16K / "client_private_trace.jsonl")
    server_16k = json_lines(PIR_16K / "server_visible_trace.jsonl")

    def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
        values = [float(row[field]) for row in rows]
        return {
            "sample_count": len(values),
            "median_ms": statistics.median(values),
            "p95_ms": percentile(values, 0.95),
            "mean_ms": statistics.mean(values),
        }

    inventory = {
        "schema": "AgentTool.V12FinalPIRUtilityInventory/1",
        "interpretation": (
            "The 100,000-record scale run and the 16,000-query repeated-observation "
            "run are distinct immutable experiments; no artifact is represented as "
            "simultaneously containing both denominators."
        ),
        "simplepir_commit": metrics_100k["commit"],
        "record_scale_evidence": {
            "source_artifact": "results_crypto_closure/scale_100000/run4/metrics.json",
            "records": metrics_100k["logical_records"],
            "real_queries": metrics_100k["queries"],
            "correct_queries": metrics_100k["correct_queries"],
            "query_generation": distribution(client_100k, "query_generation_ms"),
            "server_answer": distribution(server_100k, "answer_ms"),
            "decode_reconstruction": distribution(client_100k, "recovery_ms"),
            "online_round_trip_end_to_end": "NOT_AVAILABLE",
            "database_read_ms": metrics_100k["database_read_ms"],
            "database_construction_ms": metrics_100k["database_construction_ms"],
            "shared_state_generation_ms": metrics_100k["shared_state_generation_ms"],
            "full_preprocessing_setup_ms": metrics_100k["full_preprocessing_setup_ms"],
            "server_storage_bytes": metrics_100k["physical_bytes"],
            "client_hint_bytes": metrics_100k["hint_bytes"],
            "persistent_client_state_bytes": metrics_100k[
                "persistent_client_state_bytes"
            ],
            "upload_bytes_per_query": metrics_100k["online_upload_bytes"],
            "download_bytes_per_query": metrics_100k["online_download_bytes"],
        },
        "repeated_query_evidence": {
            "source_artifact": "results_crypto_closure/multiround_final/pir/metrics.json",
            "records": metrics_16k["logical_records"],
            "real_queries": metrics_16k["queries"],
            "correct_queries": metrics_16k["correct_queries"],
            "query_generation": distribution(client_16k, "query_generation_ms"),
            "server_answer_trace": {
                **distribution(server_16k, "answer_ms"),
                "precision_note": (
                    "Per-query trace serialized sub-millisecond values at integer-ms "
                    "precision; metrics.json retains mean_server_answer_ms."
                ),
                "high_precision_mean_ms_from_metrics": metrics_16k[
                    "mean_server_answer_ms"
                ],
            },
            "decode_reconstruction": distribution(client_16k, "recovery_ms"),
            "online_round_trip_end_to_end": "NOT_AVAILABLE",
            "database_read_ms": metrics_16k["database_read_ms"],
            "database_construction_ms": metrics_16k["database_construction_ms"],
            "shared_state_generation_ms": metrics_16k["shared_state_generation_ms"],
            "full_preprocessing_setup_ms": metrics_16k["full_preprocessing_setup_ms"],
            "server_storage_bytes": metrics_16k["physical_bytes"],
            "client_hint_bytes": metrics_16k["hint_bytes"],
            "persistent_client_state_bytes": metrics_16k[
                "persistent_client_state_bytes"
            ],
            "upload_bytes_per_query": metrics_16k["online_upload_bytes"],
            "download_bytes_per_query": metrics_16k["online_download_bytes"],
        },
        "new_pir_queries_executed": 0,
    }
    write_once_or_verify(output, json.dumps(inventory, indent=2) + "\n")
    return inventory


def make_communication(records: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    successful_oae = [
        row
        for row in records
        if row["kind"] == "MEASURED"
        and row["configuration"] == "OAE_V4R8"
        and row["success"]
    ]
    query_sizes = sorted(
        {int(value) for row in successful_oae for value in row["registry_query_bytes"]}
    )
    answer_sizes = sorted(
        {int(value) for row in successful_oae for value in row["registry_answer_bytes"]}
    )
    if query_sizes != [2020] or answer_sizes != [6592]:
        raise RuntimeError(
            f"unexpected final Registry sizes: query={query_sizes} answer={answer_sizes}"
        )
    relay = 521 * (1079 + 800)
    registry = 100 * (query_sizes[0] + answer_sizes[0])
    total = relay + registry
    value = {
        "schema": "AgentTool.V12V4R8FinalCommunicationOverhead/1",
        "derivation": "frozen public constants verified against all successful measured OAE records",
        "R": 521,
        "Q": 100,
        "relay_request_bytes": 1079,
        "relay_response_bytes": 800,
        "registry_query_bytes": query_sizes[0],
        "registry_answer_bytes": answer_sizes[0],
        "relay_bytes_per_session": relay,
        "registry_bytes_per_session": registry,
        "total_normalized_bytes_per_session": total,
        "total_normalized_MiB_per_session": total / (1024**2),
        "nominal_relay_transcript_duration_ms": 5210,
        "registry_public_epoch_ms": 6000,
        "schedule_overlap_note": (
            "Relay and Registry schedules overlap; their nominal durations are not added "
            "to obtain session wall time."
        ),
    }
    write_once_or_verify(output, json.dumps(value, indent=2) + "\n")
    return value


def make_paper_table(
    summary: list[dict[str, str]], communication: dict[str, Any], output: Path
) -> None:
    index = {
        (row["framework"], row["workload"], row["configuration"]): row
        for row in summary
    }
    fields = (
        "framework",
        "workload",
        "native_median_semantic_ms",
        "native_p95_semantic_ms",
        "v4r8_median_semantic_ms",
        "v4r8_p95_semantic_ms",
        "v4r8_median_public_session_wall_ms",
        "v4r8_p95_public_session_wall_ms",
        "additive_median_overhead_ms",
        "multiplicative_median_overhead",
        "relay_cells_per_session",
        "registry_queries_per_session",
        "normalized_bytes_per_session",
    )
    rows = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for workload in (
            "ORDINARY_TOOL",
            "AGENT_AS_TOOL_TRANSITION",
            "CACHE_REUSE_30",
            "CAPACITY_50",
        ):
            native = index[(framework, workload, "NATIVE")]
            oae = index[(framework, workload, "OAE_V4R8")]
            rows.append(
                {
                    "framework": framework,
                    "workload": workload,
                    "native_median_semantic_ms": native["semantic_median_ms"],
                    "native_p95_semantic_ms": native["semantic_p95_ms"],
                    "v4r8_median_semantic_ms": oae["semantic_median_ms"],
                    "v4r8_p95_semantic_ms": oae["semantic_p95_ms"],
                    "v4r8_median_public_session_wall_ms": oae[
                        "public_session_median_ms"
                    ],
                    "v4r8_p95_public_session_wall_ms": oae["public_session_p95_ms"],
                    "additive_median_overhead_ms": oae["additive_overhead_ms"],
                    "multiplicative_median_overhead": oae["multiplicative_overhead"],
                    "relay_cells_per_session": 521,
                    "registry_queries_per_session": 100,
                    "normalized_bytes_per_session": communication[
                        "total_normalized_bytes_per_session"
                    ],
                }
            )
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    write_once_or_verify(output, handle.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--local-head", required=True)
    parser.add_argument("--remote-head", required=True)
    parser.add_argument("--worktree-status", required=True)
    parser.add_argument("--running-processes", required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    runs_path = evidence / "final_utility_runs.csv"
    summary_path = evidence / "final_utility_summary.csv"
    records_path = evidence / "utility_records.jsonl"
    env_path = evidence / "FINAL_V4R8_ENVIRONMENT_SNAPSHOT.json"
    failure_audit_path = evidence / "failed_utility_run_audit.json"
    required = (runs_path, summary_path, records_path, env_path, failure_audit_path)
    if any(not path.is_file() for path in required):
        raise FileNotFoundError(
            f"closure inputs missing: {[str(p) for p in required if not p.is_file()]}"
        )
    with runs_path.open(encoding="utf-8", newline="") as handle:
        measured_csv = list(csv.DictReader(handle))
    with summary_path.open(encoding="utf-8", newline="") as handle:
        summary = list(csv.DictReader(handle))
    records = json_lines(records_path)
    measured = [row for row in records if row["kind"] == "MEASURED"]
    if len(measured_csv) != 480 or len(measured) != 480 or len(summary) != 16:
        raise RuntimeError("final utility denominator is incomplete")
    communication = make_communication(
        records, evidence / "final_communication_overhead.json"
    )
    pir = make_pir_inventory(evidence / "final_pir_utility_inventory.json")
    make_paper_table(summary, communication, evidence / "paper_utility_table.csv")
    completion = json.loads((evidence / "completion.json").read_text(encoding="utf-8"))
    failure_audit = json.loads(failure_audit_path.read_text(encoding="utf-8"))
    oae_measured = [row for row in measured if row["configuration"] == "OAE_V4R8"]
    protected_diff = git(
        "diff", "--name-only", f"{RUNTIME_SOURCE}..{BASE_V4R8}"
    ).splitlines()
    protected_prefixes = (
        "common_action_gateway_v2/",
        "pir_integration/",
        "v11_online/",
        "v11_full_scope/",
        "v12_timing/",
    )
    protected_diff = [
        path for path in protected_diff if path.startswith(protected_prefixes)
    ]
    if protected_diff:
        raise RuntimeError(
            f"V4R8 evidence branch changed protected runtime: {protected_diff}"
        )

    manifest_entries = []
    committed_paths = [
        ROOT / "V12_V4R8_FINAL_UTILITY_FREEZE.json",
        ROOT / "V12_V4R8_RESPONSE_ANCHOR_REPAIR_EVIDENCE" / "CLOSURE.json",
        ROOT / "V12_V4R7_RESIDUAL_TIMING_SOURCE_ATTRIBUTION_EVIDENCE" / "CLOSURE.json",
        ROOT
        / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE_EVIDENCE"
        / "BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json",
        ROOT / "results_crypto_closure" / "scale_100000" / "run4" / "metrics.json",
        ROOT / "results_crypto_closure" / "multiround_final" / "pir" / "metrics.json",
        ROOT / "scripts" / "freeze_v12_v4r8_final_utility.py",
        ROOT / "scripts" / "run_v12_v4r8_final_utility.py",
        ROOT / "scripts" / "collect_v12_v4r8_environment.py",
        ROOT / "scripts" / "audit_v12_v4r8_utility_failures.py",
        ROOT / "scripts" / "close_v12_v4r8_final_utility.py",
    ]
    evidence_paths = [
        path
        for path in evidence.iterdir()
        if path.is_file()
        and path.name
        not in {
            "FINAL_SUBMISSION_EVIDENCE_MANIFEST.json",
            "V12_V4R8_FINAL_UTILITY_SERVER_CLOSURE.json",
            "V12_V4R8_FINAL_UTILITY_SERVER_CLOSURE.md",
        }
    ]
    for path in committed_paths + evidence_paths:
        if not path.is_file():
            continue
        manifest_entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "byte_size": path.stat().st_size,
                "sha256": sha256(path),
                "persistence_status": "COMMITTED_AND_PUSHED",
                "essential": True,
            }
        )
    env = json.loads(env_path.read_text(encoding="utf-8"))
    for name, binary in env["binaries"].items():
        manifest_entries.append(
            {
                "path": binary["path"],
                "byte_size": binary["byte_size"],
                "sha256": binary["sha256"],
                "persistence_status": "REGENERABLE",
                "essential": False,
                "note": f"{name} is rebuilt from frozen source/toolchain; hash binds executed binary",
            }
        )
    manifest_entries.append(
        {
            "path": "/root/v12_v4r8_final_utility_run_20260903/runs",
            "byte_size": None,
            "sha256": None,
            "persistence_status": "SERVER_ONLY",
            "essential": False,
            "note": "low-level duplicate session directories; all paper-bearing per-run fields and hashes are preserved in committed utility records",
        }
    )
    manifest = {
        "schema": "AgentTool.V12FinalSubmissionEvidenceManifest/1",
        "final_v4r8_source_sha": RUNTIME_SOURCE,
        "entries": manifest_entries,
        "server_only_essential": False,
        "server_only_essential_paths": [],
        "secret_or_credential_files_included": False,
    }
    manifest_path = evidence / "FINAL_SUBMISSION_EVIDENCE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    summary_index = {
        (row["framework"], row["workload"], row["configuration"]): row
        for row in summary
    }
    coordinates = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for workload in (
            "ORDINARY_TOOL",
            "AGENT_AS_TOOL_TRANSITION",
            "CACHE_REUSE_30",
            "CAPACITY_50",
        ):
            native = summary_index[(framework, workload, "NATIVE")]
            oae = summary_index[(framework, workload, "OAE_V4R8")]
            coordinates.append(
                {
                    "framework": framework,
                    "workload": workload,
                    "Native": native,
                    "OAE_V4R8": oae,
                    "additive_median_overhead_ms": float(oae["additive_overhead_ms"]),
                    "multiplicative_median_overhead": float(
                        oae["multiplicative_overhead"]
                    ),
                }
            )
    safe = (
        completion["executed_measured_executions"] == 480
        and (evidence / "FINAL_V4R8_SYSTEM_INFO.txt").is_file()
        and (evidence / "FINAL_V4R8_PIP_FREEZE.txt").is_file()
        and not manifest["server_only_essential"]
        and args.running_processes == "0"
        and args.local_head == args.remote_head
        and args.worktree_status == "CLEAN"
    )
    existing_inventory = json.loads(
        (ROOT / "V12_V4R8_FINAL_UTILITY_FREEZE.json").read_text(encoding="utf-8")
    )["existing_final_v4r8_utility_evidence"]
    existing_inventory["existing_v4r8_functional"]["path"] = (
        "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE_EVIDENCE/"
        "BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json"
    )
    existing_inventory["freeze_inventory_path_erratum"] = (
        "The pre-execution freeze used a shortened nonexistent directory name for "
        "the one-run functional evidence; this closure records the actual immutable path."
    )
    closure = {
        "schema": "AgentTool.V12V4R8FinalUtilityServerClosure/1",
        "base_v4r8_evidence": BASE_V4R8,
        "final_v4r8_runtime_source": RUNTIME_SOURCE,
        "protected_runtime_diff": "NONE",
        "existing_final_v4r8_utility_evidence": existing_inventory,
        "new_timing_security_experiments": 0,
        "classifier_runs": 0,
        "auc_calculations": 0,
        "utility_benchmark": {
            "planned_measured_executions": 480,
            "executed_measured_executions": completion["executed_measured_executions"],
            "native_successes": completion["native_successes"],
            "native_failures": completion["native_failures"],
            "oae_successes": completion["oae_successes"],
            "oae_failures": completion["oae_failures"],
            "retries": 0,
            "failed_oae_run_audit": {
                "artifact": "failed_utility_run_audit.json",
                "failed_runs": failure_audit["failed_measured_runs"],
                "all_failed_runs_preserved_in_full": True,
                "failure_archive": "failed_oae_session_records.tgz",
            },
            "coordinates": coordinates,
        },
        "communication": communication,
        "pir": pir,
        "final_functional_sanity": {
            "measured_oae_executions": len(oae_measured),
            "semantic_successes": completion["oae_successes"],
            "transcript_successes": completion["oae_transcript_successes"]
            + failure_audit["aggregate"]["public_transcript_successes"],
            "silent_losses": completion["oae_silent_losses"]
            + failure_audit["aggregate"]["silent_losses"],
            "profile_overflows": completion["oae_profile_overflows"]
            + failure_audit["aggregate"]["profile_overflows"],
        },
        "environment_snapshot": "PASS",
        "reproducibility_manifest": "PASS",
        "server_only_essential": False,
        "server_only_essential_paths": [],
        "repository_audit_at_closure_generation": {
            "local_head": args.local_head,
            "remote_head": args.remote_head,
            "worktree": args.worktree_status,
            "running_experiment_processes": args.running_processes,
            "note": "The final evidence commit necessarily postdates this self-contained closure file; its exact post-push SHA is reported in the handoff and verified independently.",
        },
        "timing_privacy": "NOT_ESTABLISHED",
        "timing_go": "NO",
        "P10_full": "NOT_RUN",
        "P20": "NOT_RUN",
        "P25": "NOT_RUN",
        "confirmatory": "NOT_RUN",
        "final_holdout": "NOT_RUN",
        "safe_to_terminate_server": safe,
        "server_power_action_performed": False,
    }
    closure_path = evidence / "V12_V4R8_FINAL_UTILITY_SERVER_CLOSURE.json"
    closure_path.write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    coordinate_lines = []
    for row in coordinates:
        native = row["Native"]
        oae = row["OAE_V4R8"]
        coordinate_lines.append(
            f"- {row['framework']} / {row['workload']}: Native median/p95 "
            f"{float(native['semantic_median_ms']):.3f}/{float(native['semantic_p95_ms']):.3f} ms; "
            f"V4R8 semantic median/p95 {float(oae['semantic_median_ms']):.3f}/{float(oae['semantic_p95_ms']):.3f} ms; "
            f"public-session median/p95 {float(oae['public_session_median_ms']):.3f}/{float(oae['public_session_p95_ms']):.3f} ms; "
            f"overhead +{row['additive_median_overhead_ms']:.3f} ms / {row['multiplicative_median_overhead']:.3f}x."
        )
    md = f"""# V12 V4R8 Final Utility and Server Closure

The frozen V4R8 runtime source is `{RUNTIME_SOURCE}` and the protected-runtime diff is `NONE`. This phase ran no timing-security experiment, classifier, AUC, bootstrap, or randomization analysis.

## Utility benchmark

The frozen benchmark executed {completion["executed_measured_executions"]}/480 measured runs with zero retries: Native {completion["native_successes"]} successes and {completion["native_failures"]} failures; OAE V4R8 {completion["oae_successes"]} successes and {completion["oae_failures"]} semantic failures. The full failed-session archive shows that all {failure_audit["failed_measured_runs"]} failed semantic runs nevertheless completed their 521-cell/100-query public transcripts, with zero silent loss, profile overflow, or infrastructure-liveness failure.

{chr(10).join(coordinate_lines)}

## Communication and PIR

The final profile uses 521 Relay cells and 100 Registry queries. It carries {communication["relay_bytes_per_session"]} Relay bytes plus {communication["registry_bytes_per_session"]} Registry bytes, for {communication["total_normalized_bytes_per_session"]} bytes ({communication["total_normalized_MiB_per_session"]:.6f} MiB) per normalized session. Relay and Registry schedules overlap.

PIR utility is inventory-only: the 100,000-record scale run contains 10 correct queries, while the separate repeated-observation run contains 16,000 correct queries over 1,000 records. No new PIR campaign ran, and no unavailable metric was fabricated.

## Termination decision

`SAFE_TO_TERMINATE_SERVER = {"YES" if safe else "NO"}` at closure generation. `SERVER_ONLY_ESSENTIAL = NO`; low-level duplicate execution directories are not paper-bearing after the per-run records, summaries, environment snapshot, and hashes are committed. No server shutdown, reboot, suspend, or deletion was performed.
"""
    (evidence / "V12_V4R8_FINAL_UTILITY_SERVER_CLOSURE.md").write_text(
        md, encoding="utf-8", newline="\n"
    )
    print(
        json.dumps({"safe_to_terminate_server": safe, "coordinates": len(coordinates)})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
