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
from v11_online.session import CanonicalOnlineSession, OnlineSessionFailure
from v12_timing.collector_integrity import v4r7_public_transcript_contract
from v12_timing.isolated_tasks import FRAMEWORKS, workload_manifest
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    TIMING_ONLY_VIEW,
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)
from v12_timing.sentinel_resume import (
    TOTAL_SESSIONS,
    build_resume_workload,
    p10_profile,
    validate_freeze_manifest,
)

SESSION_SCHEMA = "AgentTool.V12P10TimingSentinelResumeSession/1"
COLLECTION_SCHEMA = "AgentTool.V12P10TimingSentinelResumeCollection/1"
DATASET_SCHEMA = "AgentTool.V12P10TimingSentinelResumeDatasetManifest/1"
ABORT_SCHEMA = "AgentTool.V12P10TimingSentinelResumeCommonAbort/1"
SESSION_RECORD_FILENAME = "sentinel_resume_session_record.json"


class CommonIntegrityFailure(RuntimeError):
    pass


class IsolatedSessionFailure(RuntimeError):
    def __init__(self, category: str, original: BaseException | None = None) -> None:
        super().__init__(category if original is None else f"{category}: {original}")
        self.category = category
        self.original = original


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
        raise CommonIntegrityFailure(
            "collector repository commit differs from frozen execution source"
        )
    for relative, expected in manifest["analysis_hashes"].items():
        path = ROOT / str(relative)
        if not path.is_file() or sha256(path) != expected:
            raise CommonIntegrityFailure(
                f"frozen collection/analysis source hash mismatch: {relative}"
            )


def _verify_workload(expected: Mapping[str, Any], workload: Any) -> None:
    actual = workload_manifest(workload)
    for key, value in actual.items():
        if expected.get(key) != value:
            raise CommonIntegrityFailure(
                f"frozen workload reconstruction mismatch for {workload.identity}: {key}"
            )


def _failure_category(error: BaseException) -> str:
    message = str(error)
    for category in (
        "SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT",
        "PIR_REAL_RESOLUTION_ADMISSION_CLOSED",
        "PROFILE_ADMISSION_CLOSED",
        "PIR_COVER_SCHEDULE_FAILURE",
    ):
        if category in message:
            return category
    if isinstance(error, TimeoutError):
        return "INFRASTRUCTURE_OR_SESSION_TIMEOUT"
    if isinstance(error, OnlineSessionFailure):
        return "ONLINE_SESSION_FAILURE"
    if isinstance(error, AssertionError):
        return "FRAMEWORK_SEMANTIC_COMPLETION_FAILURE"
    return "ISOLATED_FRAMEWORK_OR_SESSION_EXCEPTION"


def _existing_hashes(unit_root: Path) -> dict[str, str]:
    output: dict[str, str] = {}
    for relative in (
        "go_online_result.json",
        "pir/online_query_summary.json",
        "pir/server_visible_trace.jsonl",
        "pir/private_pir_cover_schedule.json",
        "online_session_lifecycle.jsonl",
    ):
        path = unit_root / relative
        if path.is_file():
            output[relative] = sha256(path)
    return output


def _base_record(expected: Mapping[str, Any], workload: Any, *, profile_id: str) -> dict[str, Any]:
    return {
        "schema": SESSION_SCHEMA,
        "identity": workload.identity,
        "task_id": workload.task_id,
        "framework": workload.framework,
        "label": workload.label,
        "profile_id": profile_id,
        "planned_block": int(expected["planned_block"]),
        "workload_block": workload.block,
        "pair_id": expected["pair_id"],
        "partition": expected["partition"],
        "selection_priority": int(expected["selection_priority"]),
        "execution_ordinal": int(expected["execution_ordinal"]),
        "claim_observers": list(expected["claim_observers"]),
        "classifier_feature_exclusions": [
            "identity",
            "task_id",
            "framework",
            "label",
            "status",
            "failure_category",
            "planned_block",
            "workload_block",
            "pair_id",
            "partition",
            "selection_priority",
            "execution_ordinal",
            "absolute_wall_clock",
            "platform_diagnostics",
        ],
    }


def _failed_record(
    unit_root: Path,
    expected: Mapping[str, Any],
    workload: Any,
    *,
    profile_id: str,
    error: BaseException,
) -> dict[str, Any]:
    record = _base_record(expected, workload, profile_id=profile_id)
    record.update(
        {
            "status": "FAILED",
            "failure_category": _failure_category(error),
            "exception_class": type(error).__name__,
            "exception_string": str(error),
            "traceback": traceback.format_exc(),
            "observer_projections": {},
            "timing_classifier_eligible": False,
            "raw_evidence_hashes": _existing_hashes(unit_root),
        }
    )
    return record


def _collect_one(unit_root: Path, expected: Mapping[str, Any], *, profile: Any) -> dict[str, Any]:
    workload = build_resume_workload(
        str(expected["task_id"]),
        str(expected["framework"]),
        int(expected["label"]),
        planned_block=int(expected["planned_block"]),
    )
    if workload.identity != expected["identity"]:
        raise CommonIntegrityFailure("frozen resume identity reconstruction failed")
    _verify_workload(expected, workload)
    cases = list(workload.cases)
    prewarm_framework(workload.framework)
    session: CanonicalOnlineSession | None = None
    try:
        with CanonicalOnlineSession(unit_root, cases, public_profile=profile) as session:
            canonical = run_online_framework_workflow(
                workload.framework, workload.workflow, cases, session.implementation()
            )
    except CommonIntegrityFailure:
        raise
    except Exception as error:  # noqa: BLE001 - frozen isolated-failure channel
        return _failed_record(
            unit_root,
            expected,
            workload,
            profile_id=profile.profile_id,
            error=error,
        )
    if session is None or session.trace is None:
        raise CommonIntegrityFailure("completed sentinel session produced no public trace")

    trace = session.trace
    pir_root = unit_root / "pir"
    summary_path = pir_root / "online_query_summary.json"
    registry_path = pir_root / "server_visible_trace.jsonl"
    cover_path = pir_root / "private_pir_cover_schedule.json"
    required = (summary_path, registry_path, cover_path, unit_root / "go_online_result.json")
    if any(not path.is_file() for path in required):
        raise CommonIntegrityFailure("completed session is missing required raw evidence")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    registry_rows = load_registry_server_trace(registry_path)
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    relay_events = list(trace.get("public_relay_events", []))
    duplex_timing = str(profile.timing_semantic_revision).startswith(
        "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_"
    )

    structural_checks = {
        "profile_id_exact": str(trace.get("profile_id")) == profile.profile_id,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "exact_R_cells": int(trace.get("emitted_cells", -1))
        == profile.total_rounds
        == len(relay_events),
        "exact_Q_queries": int(summary.get("query_count", -1)) == 100 == len(registry_rows),
        "complete_relay_response_send_ns": all(
            int(row.get("response_send_ns", 0)) > 0 for row in relay_events
        ),
        "complete_duplex_relay_boundaries": (not duplex_timing)
        or all(
            all(
                int(row.get(field, 0)) > 0
                for field in (
                    "client_to_relay_receive_ns",
                    "relay_to_gateway_send_ns",
                    "gateway_to_relay_receive_ns",
                    "relay_to_client_send_ns",
                )
            )
            for row in relay_events
        ),
        "gateway_response_clock_complete": (not duplex_timing)
        or len(trace.get("gateway_response_releases", [])) == profile.total_rounds,
        "complete_registry_response_send_ns": all(
            int(row.get("response_send_ns", 0)) > 0 for row in registry_rows
        ),
        "fixed_request_size": all(int(row["request_length"]) == 1079 for row in relay_events),
        "fixed_response_size": all(int(row["response_length"]) == 800 for row in relay_events),
        "complete_unique_relay_slot_set": len(relay_events) == profile.total_rounds
        and sorted(int(row["round"]) for row in relay_events)
        == list(range(1, profile.total_rounds + 1)),
        "fixed_registry_query_order": [int(row["ordinal"]) for row in registry_rows]
        == list(range(100)),
        "no_out_of_schedule_PIR": len(cover) == 100
        and all(int(row["ordinal"]) == index for index, row in enumerate(cover)),
    }
    response_diagnostics: dict[str, Any] = {
        "response_deadline_miss_count": 0,
        "response_release_slip_ns": [],
        "maximum_response_release_slip_ns": 0,
        "deadline_slip_is_integrity_failure": False,
    }
    if duplex_timing:
        v4r7_checks, response_diagnostics = v4r7_public_transcript_contract(
            trace,
            registry_rows,
            cover,
            expected_rounds=profile.total_rounds,
            expected_queries=profile.pir_resolution_opportunities,
            response_period_ms=profile.round_period_ms,
            expected_request_bytes=1079,
            expected_response_bytes=800,
        )
        structural_checks.update(v4r7_checks)
    failed_structural = [key for key, value in structural_checks.items() if not value]
    if failed_structural:
        raise CommonIntegrityFailure(
            "broken public-profile/instrumentation contract: " + ",".join(failed_structural)
        )
    try:
        relay_projection = relay_timing_projection(
            {"public_relay_events": relay_events},
            expected_rounds=profile.total_rounds,
            require_complete_application_timing=True,
            expected_request_bytes=1079,
            expected_response_bytes=800,
            require_duplex_application_timing=duplex_timing,
        )
        registry_projection = registry_timing_projection(
            registry_rows,
            profile_id=profile.profile_id,
            pir_period_ms=profile.pir_resolution_period_ms,
            opportunities=profile.pir_resolution_opportunities,
            require_complete_application_timing=True,
        )
    except Exception as error:
        raise CommonIntegrityFailure(f"complete timing projection defect: {error}") from error
    expected_relay_view = DUPLEX_TIMING_ONLY_VIEW if duplex_timing else TIMING_ONLY_VIEW
    if relay_projection["view"] != expected_relay_view or registry_projection["view"] != TIMING_ONLY_VIEW:
        raise CommonIntegrityFailure("completed session projection did not use TIMING_ONLY_VIEW")
    relay_keys = (
        (
            "slot_indexed_session_relative_client_to_relay_receive_ns",
            "chronological_client_to_relay_receive_inter_arrival_ns",
            "slot_indexed_session_relative_relay_to_gateway_send_ns",
            "chronological_relay_to_gateway_send_inter_arrival_ns",
            "slot_indexed_session_relative_gateway_to_relay_receive_ns",
            "chronological_gateway_to_relay_receive_inter_arrival_ns",
            "slot_indexed_session_relative_relay_to_client_send_ns",
            "chronological_relay_to_client_send_inter_arrival_ns",
            "slot_paired_client_relay_to_gateway_ns",
            "slot_paired_gateway_roundtrip_ns",
            "slot_paired_relay_response_forward_ns",
        )
        if duplex_timing
        else (
            "slot_indexed_session_relative_request_ns",
            "chronological_request_inter_arrival_ns",
            "slot_indexed_session_relative_response_send_ns",
            "chronological_response_send_inter_arrival_ns",
            "slot_paired_request_response_ns",
        )
    )
    relay_widths = tuple(len(relay_projection[key]) for key in relay_keys)
    public_r = profile.total_rounds
    expected_relay_widths = (
        (
            public_r,
            public_r - 1,
            public_r,
            public_r - 1,
            public_r,
            public_r - 1,
            public_r,
            public_r - 1,
            public_r,
            public_r,
            public_r,
        )
        if duplex_timing
        else (public_r, public_r - 1, public_r, public_r - 1, public_r)
    )
    if relay_widths != expected_relay_widths:
        raise CommonIntegrityFailure("completed Relay raw feature widths drifted")

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
    semantic_checks = {
        "canonical_operation_ids_exact": _trajectory_ids(canonical) == expected_ids,
        "operation_ids_recovered_exact": recovered == expected_ids,
        "causal_order_exact": delivered == expected_ids,
        "causal_proof": session.causal_proof()["passed"] is True,
        "real_resolution_count": int(summary.get("real_query_count", -1)) == len(unique_agents),
        "trusted_cache_hit_count": int(summary.get("descriptor_cache_hits", -1))
        == expected_cache_hits,
        "real_plus_dummy_Q": int(summary.get("real_query_count", -1))
        + int(summary.get("dummy_query_count", -1))
        == 100,
        "external_accepted_ids": sorted(trace.get("accepted_operation_ids", []))
        == sorted(external_ids),
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
        "no_infrastructure_liveness_failure": trace.get("infrastructure_liveness_failure")
        is False,
    }
    failed_semantic = [key for key, value in semantic_checks.items() if not value]
    if failed_semantic:
        error = IsolatedSessionFailure(
            "SEMANTIC_OR_SESSION_INTEGRITY_FAILURE:" + ",".join(failed_semantic)
        )
        return _failed_record(
            unit_root,
            expected,
            workload,
            profile_id=profile.profile_id,
            error=error,
        )

    projections = {
        observer: relay_projection if observer == "RELAY" else registry_projection
        for observer in expected["claim_observers"]
    }
    launches = list(trace.get("slot_launches", []))
    record = _base_record(expected, workload, profile_id=profile.profile_id)
    record.update(
        {
            "status": "COMPLETE",
            "failure_category": None,
            "functional_integrity": {**structural_checks, **semantic_checks},
            "functional_integrity_pass": True,
            "timing_classifier_eligible": True,
            "observer_projections": projections,
            "platform_diagnostics": {
                "nominal_late_cells": int(trace.get("nominal_late_cells", 0)),
                "launch_slip_ns": [int(row.get("launch_slip_ns", 0)) for row in launches],
                "relay_request_gap_ns": list(
                    relay_projection["chronological_request_inter_arrival_ns"]
                ),
                "relay_response_send_gap_ns": list(
                    relay_projection["chronological_response_send_inter_arrival_ns"]
                ),
                "registry_query_gap_ns": list(registry_projection["inter_query_gap_ns"]),
                "registry_request_response_ns": list(
                    registry_projection["query_response_ns"]
                ),
                "infrastructure_liveness_failure": False,
                **response_diagnostics,
            },
            "raw_evidence_hashes": _existing_hashes(unit_root),
        }
    )
    return record


def _close_dataset(
    output: Path,
    manifest_path: Path,
    record_inventory: list[dict[str, Any]],
    ledger_path: Path,
    *,
    common_abort: bool,
) -> dict[str, Any]:
    dataset: dict[str, Any] = {
        "schema": DATASET_SCHEMA,
        "collection_closed": True,
        "common_integrity_abort": common_abort,
        "frozen_manifest_sha256": sha256(manifest_path),
        "session_records": record_inventory,
        "session_record_count": len(record_inventory),
        "execution_ledger_sha256": sha256(ledger_path) if ledger_path.is_file() else None,
    }
    dataset["dataset_inventory_sha256"] = canonical_sha256(record_inventory)
    write_json(output / "dataset_manifest.json", dataset)
    return dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect the frozen serial fresh P10 resume sentinel.")
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
        "schema": COLLECTION_SCHEMA,
        "manifest_sha256": sha256(args.manifest),
        "execution_source_commit": manifest["execution_source_commit"],
        "expected_sessions": TOTAL_SESSIONS,
        "executed_sessions": 0,
        "complete_sessions": 0,
        "failed_sessions": 0,
        "retries": 0,
        "serial_same_host_execution": True,
        "classifier_training_during_collection": 0,
        "auc_calculations_during_collection": 0,
        "bootstrap_runs_during_collection": 0,
        "status": "COLLECTION_OPEN",
        "started_ns": time.time_ns(),
    }
    write_json(args.output / "collection_state.json", campaign)
    for framework in FRAMEWORKS:
        prewarm_framework(framework)
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    ledger_path = args.output / "execution_ledger.jsonl"
    record_inventory: list[dict[str, Any]] = []
    previous_ledger_hash = "0" * 64
    for schedule_row in schedule:
        identity = str(schedule_row["identity"])
        expected = dict(identities[identity])
        expected.update(schedule_row)
        ordinal = int(schedule_row["execution_ordinal"])
        unit_root = args.output / "sessions" / f"{ordinal:04d}_{identity}"
        started_ns = time.time_ns()
        common_error: BaseException | None = None
        try:
            record = _collect_one(unit_root, expected, profile=profile)
        except CommonIntegrityFailure as error:
            common_error = error
            workload = build_resume_workload(
                str(expected["task_id"]),
                str(expected["framework"]),
                int(expected["label"]),
                planned_block=int(expected["planned_block"]),
            )
            record = _failed_record(
                unit_root,
                expected,
                workload,
                profile_id=profile.profile_id,
                error=error,
            )
            record["failure_category"] = "COMMON_CAMPAIGN_INTEGRITY_FAILURE"
        record_path = unit_root / SESSION_RECORD_FILENAME
        write_json(record_path, record)
        record_hash = sha256(record_path)
        ledger_row = {
            "execution_ordinal": ordinal,
            "identity": identity,
            "coordinate_id": schedule_row["coordinate_id"],
            "pair_id": schedule_row["pair_id"],
            "planned_block": schedule_row["planned_block"],
            "partition": schedule_row["partition"],
            "status": record["status"],
            "failure_category": record["failure_category"],
            "started_ns": started_ns,
            "ended_ns": time.time_ns(),
            "record_path": record_path.relative_to(args.output).as_posix(),
            "record_sha256": record_hash,
            "previous_ledger_record_sha256": previous_ledger_hash,
        }
        encoded = json.dumps(ledger_row, sort_keys=True, separators=(",", ":"))
        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
        previous_ledger_hash = hashlib.sha256(encoded.encode()).hexdigest()
        record_inventory.append(
            {
                "identity": identity,
                "status": record["status"],
                "failure_category": record["failure_category"],
                "path": ledger_row["record_path"],
                "sha256": record_hash,
            }
        )
        campaign["executed_sessions"] = ordinal + 1
        campaign["complete_sessions"] += record["status"] == "COMPLETE"
        campaign["failed_sessions"] += record["status"] == "FAILED"
        campaign["last_ledger_record_sha256"] = previous_ledger_hash
        write_json(args.output / "collection_state.json", campaign)
        if common_error is not None:
            dataset = _close_dataset(
                args.output,
                args.manifest,
                record_inventory,
                ledger_path,
                common_abort=True,
            )
            abort = {
                "schema": ABORT_SCHEMA,
                "status": "ABORTED_COMMON_INTEGRITY_FAILURE",
                "identity": identity,
                "execution_ordinal": ordinal,
                "executed_sessions": campaign["executed_sessions"],
                "exception_class": type(common_error).__name__,
                "exception_string": str(common_error),
                "identity_consumed_no_retry": True,
                "retries": 0,
                "classifier_training_runs": 0,
                "auc_calculations": 0,
            }
            write_json(args.output / "campaign_abort.json", abort)
            campaign.update(
                {
                    "status": "ABORTED_COMMON_INTEGRITY_FAILURE",
                    "ended_ns": time.time_ns(),
                    "dataset_manifest_sha256": sha256(args.output / "dataset_manifest.json"),
                    "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
                }
            )
            write_json(args.output / "collection_state.json", campaign)
            return 2
    if len(record_inventory) != TOTAL_SESSIONS:
        raise AssertionError("resume sentinel collection closed without all frozen sessions")
    dataset = _close_dataset(
        args.output, args.manifest, record_inventory, ledger_path, common_abort=False
    )
    campaign.update(
        {
            "status": "COLLECTION_CLOSED_COMPLETE",
            "executed_sessions": TOTAL_SESSIONS,
            "ended_ns": time.time_ns(),
            "retries": 0,
            "dataset_manifest_sha256": sha256(args.output / "dataset_manifest.json"),
            "dataset_inventory_sha256": dataset["dataset_inventory_sha256"],
        }
    )
    write_json(args.output / "campaign_completion.json", campaign)
    write_json(args.output / "collection_state.json", campaign)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
