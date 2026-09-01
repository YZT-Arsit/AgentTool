from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_online.frameworks import prewarm_framework, run_online_framework_workflow
from v11_online.session import CanonicalOnlineSession
from v12_timing.isolated_tasks import workload_manifest
from v12_timing.projection import (
    TIMING_ONLY_VIEW,
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)
from v12_timing.sentinel import (
    FRAMEWORKS,
    build_sentinel_workload,
    p10_profile,
    validate_freeze_manifest,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _trajectory_ids(result: Mapping[str, Any]) -> list[str]:
    return [str(row["operation_id"]) for row in result["projection"]["trajectory"]]


def _verify_execution_source(manifest: Mapping[str, Any]) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != manifest["execution_source_commit"]:
        raise RuntimeError("collector repository commit differs from the frozen execution source")
    for relative, expected in manifest["analysis_hashes"].items():
        path = ROOT / str(relative)
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"frozen collection/analysis source hash mismatch: {relative}")


def _verify_workload(expected: Mapping[str, Any], workload: Any) -> None:
    actual = workload_manifest(workload)
    for key, value in actual.items():
        if expected.get(key) != value:
            raise RuntimeError(f"frozen workload reconstruction mismatch for {workload.identity}: {key}")


def _collect_one(
    unit_root: Path,
    expected: Mapping[str, Any],
    *,
    profile: Any,
) -> dict[str, Any]:
    workload = build_sentinel_workload(
        str(expected["task_id"]),
        str(expected["framework"]),
        int(expected["label"]),
        block=int(expected["block"]),
    )
    if workload.identity != expected["identity"]:
        raise RuntimeError("frozen sentinel identity reconstruction failed")
    _verify_workload(expected, workload)
    cases = list(workload.cases)
    prewarm_framework(workload.framework)
    with CanonicalOnlineSession(unit_root, cases, public_profile=profile) as session:
        canonical = run_online_framework_workflow(
            workload.framework, workload.workflow, cases, session.implementation()
        )
    if session.trace is None:
        raise RuntimeError("sentinel session produced no public trace")
    trace = session.trace
    pir_root = unit_root / "pir"
    summary_path = pir_root / "online_query_summary.json"
    registry_path = pir_root / "server_visible_trace.jsonl"
    cover_path = pir_root / "private_pir_cover_schedule.json"
    go_path = unit_root / "go_online_result.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    registry_rows = load_registry_server_trace(registry_path)
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    relay_events = list(trace.get("public_relay_events", []))
    relay_projection = relay_timing_projection(
        {"public_relay_events": relay_events},
        expected_rounds=profile.total_rounds,
        require_complete_application_timing=True,
    )
    registry_projection = registry_timing_projection(
        registry_rows,
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
        require_complete_application_timing=True,
    )
    expected_ids = [case.operation_id for case in cases]
    external_ids = [case.operation_id for case in cases if case.placement != "TRUSTED_MODULE_LOCAL"]
    unique_agents = {case.agent_id for case in cases}
    expected_cache_hits = len(cases) - len(unique_agents)
    recovered = [
        str(row["operation_id"])
        for row in session.lifecycle
        if row["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"
    ]
    delivered = [
        str(row["operation_id"])
        for row in session.lifecycle
        if row["stage"] == "FRAMEWORK_RESULT_DELIVERED"
    ]
    checks = {
        "profile_id_exact": str(trace.get("profile_id")) == profile.profile_id,
        "canonical_operation_ids_exact": _trajectory_ids(canonical) == expected_ids,
        "operation_ids_recovered_exact": recovered == expected_ids,
        "causal_order_exact": delivered == expected_ids,
        "causal_proof": session.causal_proof()["passed"] is True,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "exact_R_cells": int(trace.get("emitted_cells", -1)) == 506 == len(relay_events),
        "exact_Q_queries": int(summary.get("query_count", -1)) == 100 == len(registry_rows),
        "complete_relay_response_send_ns": all(
            int(row.get("response_send_ns", 0)) > 0 for row in relay_events
        ),
        "complete_registry_response_send_ns": all(
            int(row.get("response_send_ns", 0)) > 0 for row in registry_rows
        ),
        "complete_timing_views": relay_projection["view"] == registry_projection["view"] == TIMING_ONLY_VIEW,
        "fixed_request_size": all(int(row["request_length"]) == 1079 for row in relay_events),
        "fixed_response_size": all(int(row["response_length"]) == 800 for row in relay_events),
        "fixed_relay_slot_order": [int(row["round"]) for row in relay_events] == list(range(1, 507)),
        "fixed_registry_query_order": [int(row["ordinal"]) for row in registry_rows] == list(range(100)),
        "no_out_of_schedule_PIR": len(cover) == 100
        and all(int(row["ordinal"]) == index for index, row in enumerate(cover)),
        "real_resolution_count": int(summary.get("real_query_count", -1)) == len(unique_agents),
        "trusted_cache_hit_count": int(summary.get("descriptor_cache_hits", -1)) == expected_cache_hits,
        "real_plus_dummy_Q": int(summary.get("real_query_count", -1))
        + int(summary.get("dummy_query_count", -1))
        == 100,
        "external_accepted_ids": sorted(trace.get("accepted_operation_ids", [])) == sorted(external_ids),
        "external_result_ids": sorted(
            str(row["operation_id"]) for row in trace.get("results", [])
        )
        == sorted(external_ids),
        "zero_resolved_not_admitted": trace.get("resolved_not_admitted_ids", []) == [],
        "zero_profile_overflow": int(trace.get("profile_overflow_events", -1)) == 0,
        "zero_silent_committed_result_loss": int(
            trace.get("silent_committed_result_losses", -1)
        )
        == 0,
        "zero_dummy_provider_operations": int(trace.get("dummy_provider_operations", -1)) == 0,
        "no_infrastructure_liveness_failure": trace.get("infrastructure_liveness_failure") is False,
    }
    projections = {
        observer: relay_projection if observer == "RELAY" else registry_projection
        for observer in expected["claim_observers"]
    }
    launches = list(trace.get("slot_launches", []))
    record = {
        "schema": "AgentTool.V12P10TimingSentinelSession/1",
        "identity": workload.identity,
        "task_id": workload.task_id,
        "framework": workload.framework,
        "profile_id": profile.profile_id,
        "block": workload.block,
        "partition": expected["partition"],
        "claim_observers": list(expected["claim_observers"]),
        "functional_integrity": checks,
        "functional_integrity_pass": all(checks.values()),
        "observer_projections": projections,
        "platform_diagnostics": {
            "nominal_late_cells": int(trace.get("nominal_late_cells", 0)),
            "launch_slip_ns": [int(row.get("launch_slip_ns", 0)) for row in launches],
            "relay_request_gap_ns": list(relay_projection["request_inter_arrival_ns"]),
            "relay_response_send_gap_ns": list(relay_projection["response_inter_arrival_ns"]),
            "registry_query_gap_ns": list(registry_projection["inter_query_gap_ns"]),
            "registry_request_response_ns": list(registry_projection["query_response_ns"]),
            "infrastructure_liveness_failure": bool(trace.get("infrastructure_liveness_failure")),
        },
        "raw_evidence_hashes": {
            "go_online_result.json": sha256(go_path),
            "pir/online_query_summary.json": sha256(summary_path),
            "pir/server_visible_trace.jsonl": sha256(registry_path),
            "pir/private_pir_cover_schedule.json": sha256(cover_path),
        },
        "classifier_feature_exclusions": [
            "identity",
            "task_id",
            "framework",
            "block",
            "partition",
            "execution_ordinal",
            "absolute_wall_clock",
            "platform_diagnostics",
        ],
    }
    write_json(unit_root / "sentinel_timing_record.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect the frozen serial P10 sentinel dataset.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite or resume sentinel campaign: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest)
    _verify_execution_source(manifest)
    profile = p10_profile()
    args.output.mkdir(parents=True)
    (args.output / "frozen_manifest.json").write_bytes(args.manifest.read_bytes())
    campaign: dict[str, Any] = {
        "schema": "AgentTool.V12P10TimingSentinelCollection/1",
        "manifest_sha256": sha256(args.manifest),
        "execution_source_commit": manifest["execution_source_commit"],
        "expected_sessions": 4800,
        "completed_sessions": 0,
        "retries": 0,
        "serial_same_host_execution": True,
        "classifier_training_during_collection": 0,
        "auc_calculations_during_collection": 0,
        "status": "COLLECTION_OPEN",
        "started_ns": time.time_ns(),
    }
    write_json(args.output / "collection_state.json", campaign)
    for framework in FRAMEWORKS:
        prewarm_framework(framework)
    identities = manifest["identity_manifest"]
    ledger_path = args.output / "execution_ledger.jsonl"
    record_inventory: list[dict[str, Any]] = []
    previous_ledger_hash = "0" * 64
    for schedule_row in manifest["execution_schedule"]:
        identity = str(schedule_row["identity"])
        expected = identities[identity]
        ordinal = int(schedule_row["execution_ordinal"])
        unit_root = args.output / "sessions" / f"{ordinal:04d}_{identity}"
        started_ns = time.time_ns()
        try:
            record = _collect_one(unit_root, expected, profile=profile)
        except Exception as error:  # noqa: BLE001 - every consumed identity must preserve abort evidence
            abort = {
                "schema": "AgentTool.V12P10TimingSentinelAbort/1",
                "status": "ABORTED",
                "identity": identity,
                "execution_ordinal": ordinal,
                "completed_sessions_before_failure": campaign["completed_sessions"],
                "identity_consumed_no_retry": True,
                "exception_class": type(error).__name__,
                "exception_string": str(error),
                "traceback": traceback.format_exc(),
                "classifier_training_runs": 0,
                "auc_calculations": 0,
            }
            write_json(args.output / "campaign_abort.json", abort)
            campaign.update({"status": "ABORTED", "ended_ns": time.time_ns(), "abort": abort})
            write_json(args.output / "collection_state.json", campaign)
            return 2
        record_path = unit_root / "sentinel_timing_record.json"
        record_hash = sha256(record_path)
        ledger_row = {
            "execution_ordinal": ordinal,
            "identity": identity,
            "coordinate_id": schedule_row["coordinate_id"],
            "pair_id": schedule_row["pair_id"],
            "block": schedule_row["block"],
            "partition": schedule_row["partition"],
            "started_ns": started_ns,
            "ended_ns": time.time_ns(),
            "functional_integrity_pass": record["functional_integrity_pass"],
            "record_path": record_path.relative_to(args.output).as_posix(),
            "record_sha256": record_hash,
            "previous_ledger_record_sha256": previous_ledger_hash,
        }
        encoded = json.dumps(ledger_row, sort_keys=True, separators=(",", ":"))
        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
        previous_ledger_hash = hashlib.sha256(encoded.encode()).hexdigest()
        record_inventory.append(
            {"identity": identity, "path": ledger_row["record_path"], "sha256": record_hash}
        )
        campaign["completed_sessions"] = ordinal + 1
        campaign["last_ledger_record_sha256"] = previous_ledger_hash
        write_json(args.output / "collection_state.json", campaign)
        if not record["functional_integrity_pass"]:
            failure = {
                "schema": "AgentTool.V12P10TimingSentinelFunctionalFailure/1",
                "status": "ABORTED",
                "identity": identity,
                "execution_ordinal": ordinal,
                "failed_checks": [
                    key for key, value in record["functional_integrity"].items() if not value
                ],
                "identity_consumed_no_retry": True,
            }
            write_json(args.output / "functional_failure.json", failure)
            campaign.update({"status": "ABORTED", "ended_ns": time.time_ns(), "failure": failure})
            write_json(args.output / "collection_state.json", campaign)
            return 3
    if len(record_inventory) != 4800:
        raise AssertionError("sentinel collection closed without all frozen sessions")
    dataset_manifest: dict[str, Any] = {
        "schema": "AgentTool.V12P10TimingSentinelDatasetManifest/1",
        "collection_closed": True,
        "frozen_manifest_sha256": sha256(args.manifest),
        "session_records": record_inventory,
        "session_record_count": len(record_inventory),
        "execution_ledger_sha256": sha256(ledger_path),
    }
    dataset_manifest["classifier_dataset_sha256"] = canonical_sha256(record_inventory)
    write_json(args.output / "dataset_manifest.json", dataset_manifest)
    campaign.update(
        {
            "status": "COLLECTION_CLOSED_COMPLETE",
            "completed_sessions": 4800,
            "ended_ns": time.time_ns(),
            "retries": 0,
            "dataset_manifest_sha256": sha256(args.output / "dataset_manifest.json"),
            "classifier_dataset_sha256": dataset_manifest["classifier_dataset_sha256"],
        }
    )
    write_json(args.output / "campaign_completion.json", campaign)
    write_json(args.output / "collection_state.json", campaign)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
