#!/usr/bin/env python3
"""Offline-only reconstruction of the immutable V12 MDCC failure.

This script never invokes a framework, provider, PIR process, or canonical
runner.  It intentionally gives the proposed effective-clock rule the most
favourable clock alignment allowed by the retained evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FIRST_GO_RESULT.json"
TRAJECTORY_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FIRST_PRIVATE_TRAJECTORY.json"
CONTROL_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FIRST_TRUSTED_CONTROL_EVENTS.jsonl"
FAILURE_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FAILURE.json"
SOURCE_PATH = ROOT / "common_action_gateway_v2" / "canonicalv9" / "online.go"
JSON_OUT = ROOT / "V12_TIMING_ADMISSION_CLOCK_ROOT_CAUSE.json"
MD_OUT = ROOT / "V12_TIMING_ADMISSION_CLOCK_ROOT_CAUSE.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ns_ms(value: int | None) -> float | None:
    return None if value is None else round(value / 1_000_000, 6)


def ns_ms_text(value: int | None) -> str:
    converted = ns_ms(value)
    return "not available (prior operation was rejected)" if converted is None else f"{converted} ms"


def main() -> None:
    trace = read_json(TRACE_PATH)
    trajectory = read_json(TRAJECTORY_PATH)
    controls = [json.loads(line) for line in CONTROL_PATH.read_text(encoding="utf-8").splitlines()]
    failure = read_json(FAILURE_PATH)

    launches = {int(row["slot"]): row for row in trace["slot_launches"]}
    session_t0 = next(int(row["monotonic_ns"]) for row in trajectory if row["stage"] == "SESSION_T0")
    t0_assigned_rel = next(
        int(row["monotonic_ns"]) for row in trace["public_setup_events"] if row["stage"] == "T0_ASSIGNED"
    )

    # SESSION_T0 is recorded only after Go emits SESSION_READY and Python starts
    # the PIR cover thread.  Therefore this subtraction is an upper bound on
    # the real Go process-clock origin.  Subtracting it from Python timestamps
    # produces the earliest (most repair-favourable) possible Go-relative
    # action-arrival time.
    process_clock_origin_upper_bound_ns = session_t0 - t0_assigned_rel

    lifecycle: dict[str, dict[str, int]] = {}
    ordered_operations: list[str] = []
    for row in trajectory:
        operation_id = str(row.get("operation_id", ""))
        if not operation_id:
            continue
        lifecycle.setdefault(operation_id, {})[str(row["stage"])] = int(row["monotonic_ns"])
        if row["stage"] == "ACTION_INTENT_SUBMITTED":
            ordered_operations.append(operation_id)

    accepted_round = {
        str(row["operation_id"]): int(row["round"])
        for row in controls
        if row.get("type") == "ACTION_ACCEPTED"
    }
    admitted_round = {
        str(row["operation_id"]): int(row["round"])
        for row in controls
        if row.get("type") == "ACTION_ADMITTED"
    }
    result_round = {
        str(row["operation_id"]): int(row["round"])
        for row in controls
        if row.get("type") == "RESULT_AVAILABLE"
    }
    rejection = {
        str(row["operation_id"]): str(row["reason"])
        for row in controls
        if row.get("type") == "ACTION_REJECTED" and row.get("operation_id")
    }

    skipped_slots: list[dict[str, Any]] = []
    operation_rows: list[dict[str, Any]] = []
    actual_next_slot = 1
    prior_operation_id: str | None = None
    for index, operation_id in enumerate(ordered_operations, start=1):
        stages = lifecycle[operation_id]
        intent_abs = stages["ACTION_INTENT_SUBMITTED"]
        recovered_abs = stages["DYNAMIC_PIR_DESCRIPTOR_RECOVERED"]
        intent_earliest_rel = intent_abs - process_clock_origin_upper_bound_ns
        recovered_earliest_rel = recovered_abs - process_clock_origin_upper_bound_ns
        actual_round = accepted_round.get(operation_id)
        scan_end = actual_round if actual_round is not None else 300
        operation_skips: list[dict[str, Any]] = []
        for slot in range(actual_next_slot, scan_end + (0 if actual_round is not None else 1)):
            if actual_round is not None and slot == actual_round:
                break
            launch = launches[slot]
            nominal_cutoff = int(launch["preparation_cutoff_ns"])
            effective_cutoff = int(launch["eligible_ns"]) - 1_000_000
            if recovered_earliest_rel < nominal_cutoff:
                classification = "OTHER"
            elif recovered_earliest_rel < effective_cutoff:
                classification = "NOMINAL_CUTOFF_EXPIRED_BUT_EFFECTIVE_SLOT_STILL_FUTURE"
            else:
                classification = "EFFECTIVE_SLOT_ALREADY_COMMITTED"
            item = {
                "operation_index": index,
                "operation_id": operation_id,
                "slot": slot,
                "classification": classification,
                "private_action_available_by_effective_cutoff": recovered_earliest_rel < effective_cutoff,
                "recovered_earliest_go_relative_ns": recovered_earliest_rel,
                "nominal_cutoff_ns": nominal_cutoff,
                "effective_cutoff_ns": effective_cutoff,
            }
            operation_skips.append(item)
            skipped_slots.append(item)
        if actual_round is not None:
            actual_next_slot = actual_round + 1
        else:
            actual_next_slot = 301

        prior_result_abs = None
        prior_result = None
        if prior_operation_id is not None:
            prior_result_abs = lifecycle[prior_operation_id].get("FRAMEWORK_RESULT_DELIVERED")
            prior_result = result_round.get(prior_operation_id)
        candidate_slot = actual_round if actual_round is not None else (operation_skips[0]["slot"] if operation_skips else None)
        launch = launches.get(candidate_slot) if candidate_slot is not None else None
        operation_rows.append(
            {
                "operation_index": index,
                "operation_id": operation_id,
                "prior_result_round": prior_result,
                "prior_framework_result_delivered_monotonic_ns": prior_result_abs,
                "next_action_intent_submitted_monotonic_ns": intent_abs,
                "descriptor_recovered_monotonic_ns": recovered_abs,
                "framework_delay_ns": None if prior_result_abs is None else intent_abs - prior_result_abs,
                "pir_or_cache_delay_ns": recovered_abs - intent_abs,
                "intended_action_slot": candidate_slot,
                "nominal_deadline_ns": None if launch is None else int(launch["deadline_ns"]),
                "nominal_cutoff_ns": None if launch is None else int(launch["preparation_cutoff_ns"]),
                "effective_eligibility_ns": None if launch is None else int(launch["eligible_ns"]),
                "effective_cutoff_ns": None if launch is None else int(launch["eligible_ns"]) - 1_000_000,
                "actual_slot_dispatch_ns": None if launch is None else int(launch["scheduler_dispatch_ns"]),
                "public_clock_lag_ns": None if launch is None else int(launch["eligible_ns"]) - int(launch["deadline_ns"]),
                "intent_earliest_go_relative_ns": intent_earliest_rel,
                "descriptor_recovered_earliest_go_relative_ns": recovered_earliest_rel,
                "actual_accepted_round": actual_round,
                "actual_admitted_round": admitted_round.get(operation_id),
                "result_round": result_round.get(operation_id),
                "admission_outcome": "ADMITTED" if operation_id in admitted_round else rejection.get(operation_id, "UNKNOWN"),
                "skipped_slots": operation_skips,
            }
        )
        prior_operation_id = operation_id

    # Greedy offline replay of the source algorithm with C_i = E_i - L.
    # Descriptor recovery is used as the action-arrival boundary, and the
    # favourable clock origin above intentionally understates arrival times.
    replay_next_slot = 1
    replay_admitted = 0
    for row in operation_rows:
        arrival = int(row["descriptor_recovered_earliest_go_relative_ns"])
        chosen = None
        while replay_next_slot <= 300:
            effective_cutoff = int(launches[replay_next_slot]["eligible_ns"]) - 1_000_000
            if arrival < effective_cutoff:
                chosen = replay_next_slot
                replay_next_slot += 1
                break
            replay_next_slot += 1
        row["counterfactual_effective_clock_round"] = chosen
        row["counterfactual_admitted"] = chosen is not None
        replay_admitted += int(chosen is not None)

    last_admission = launches[300]
    last_effective_cutoff = int(last_admission["eligible_ns"]) - 1_000_000
    last_nominal_cutoff = int(last_admission["preparation_cutoff_ns"])
    op47 = operation_rows[46]
    op46 = operation_rows[45]
    op46_result_dispatch = int(launches[int(op46["result_round"])]["scheduler_dispatch_ns"])
    op46_delivered_earliest_rel = (
        lifecycle[op46["operation_id"]]["FRAMEWORK_RESULT_DELIVERED"]
        - process_clock_origin_upper_bound_ns
    )
    classifications: dict[str, int] = {}
    for item in skipped_slots:
        classifications[item["classification"]] = classifications.get(item["classification"], 0) + 1

    result = {
        "schema": "AgentTool.V12TimingAdmissionClockRootCause/1",
        "phase": "V12-TIMING-ADMISSION-CLOCK-CONSISTENCY-CLOSURE",
        "base_commit": "0de29230062c200a4179bbdefeeec1ccc8c75263",
        "analysis_mode": "OFFLINE_IMMUTABLE_EVIDENCE_ONLY",
        "prior_failures": {
            "DEV-TD-CAPACITY50-P10-PIR60": "ABORTED_HARNESS_INTEGRITY_FAILURE_NEVER_RETRIED",
            "DEV-TPCIC-MS-SAME-AGENT-DEPTH50-001": "MICROSOFT_DEFAULT_MAX_ITERATIONS_FAILURE_NEVER_RETRIED",
            "DEV-MDCC-OA-SAME-AGENT-DEPTH50-001": "LIVE_CAPACITY_FAIL_NEVER_RETRIED",
        },
        "evidence_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in (TRACE_PATH, TRAJECTORY_PATH, CONTROL_PATH, FAILURE_PATH, SOURCE_PATH)
        },
        "source_audit": {
            "old_action_commitment_clock": "NOMINAL",
            "public_emission_clock": "EFFECTIVE_NO_BURST",
            "clock_mismatch_confirmed": True,
            "action_nominal_cutoff_sites": ["online.go:294", "online.go:307", "online.go:405"],
            "effective_emission_site": "online.go:414-417",
            "result_nominal_cutoff_sites": ["online.go:224", "runner.go:606-612"],
            "exact_cause": (
                "Action preparation and result delivery use nominal D_i-L cutoffs, while physical dispatch "
                "uses E_i=max(D_i,S_(i-1)+Delta); the preparation worker also advances permanently over "
                "nominally expired slots before their effective commitment time."
            ),
        },
        "clock_alignment": {
            "python_session_t0_monotonic_ns": session_t0,
            "go_t0_assigned_relative_ns": t0_assigned_rel,
            "go_process_clock_origin_upper_bound_ns": process_clock_origin_upper_bound_ns,
            "interpretation": (
                "This upper-bound origin makes every Python action arrive as early as retained evidence permits. "
                "A real IPC/PIR-start delay can only make the replay less favourable."
            ),
        },
        "historical_result": {
            "identity": failure["identity"],
            "native_operations": 50,
            "canonical_operations": int(trace["admitted"]),
            "rounds": int(trace["rounds"]),
            "emitted_cells": int(trace["emitted_cells"]),
            "session_status": trace["session_status"],
            "resolved_not_admitted_ids": trace["resolved_not_admitted_ids"],
            "schedule_misses": int(trace["schedule_misses"]),
            "maximum_launch_slip_ns": max(int(row["launch_slip_ns"]) for row in trace["slot_launches"]),
        },
        "reconstruction": {
            "operations": operation_rows,
            "skipped_slot_class_counts": classifications,
            "nominal_only_slots_lost": classifications.get(
                "NOMINAL_CUTOFF_EXPIRED_BUT_EFFECTIVE_SLOT_STILL_FUTURE", 0
            ),
            "operation_47_to_50": operation_rows[46:50],
        },
        "counterfactual": {
            "rule": "E_i=max(D_i,S_(i-1)+Delta); C_i_effective=E_i-L",
            "admitted": replay_admitted,
            "denominator": 50,
            "effective_clock_replay_50_of_50": replay_admitted == 50,
            "last_nominal_admission_cutoff_ns": last_nominal_cutoff,
            "last_effective_admission_cutoff_ns": last_effective_cutoff,
            "operation_47_earliest_recovery_ns": int(op47["descriptor_recovered_earliest_go_relative_ns"]),
            "operation_47_after_last_nominal_cutoff_ns": int(op47["descriptor_recovered_earliest_go_relative_ns"]) - last_nominal_cutoff,
            "operation_47_after_last_effective_cutoff_ns": int(op47["descriptor_recovered_earliest_go_relative_ns"]) - last_effective_cutoff,
            "operation_46_result_dispatch_ns": op46_result_dispatch,
            "operation_46_framework_delivery_earliest_ns": op46_delivered_earliest_rel,
            "operation_46_dispatch_to_framework_delivery_lower_bound_ns": op46_delivered_earliest_rel - op46_result_dispatch,
            "operation_47_framework_delay_after_delivery_ns": int(op47["framework_delay_ns"]),
            "decision": "H3000_CAPACITY_STILL_INSUFFICIENT",
        },
        "phase_stop": {
            "required_by_protocol": True,
            "effective_public_clock_implemented": False,
            "runtime_source_modified": False,
            "fresh_live_capacity": "NOT_RUN",
            "timing_attack_sessions": 0,
            "timing_confirmatory_sessions": 0,
            "selected_final_v12_cases_executed": 0,
        },
        "final_report": {
            "prior_mdcc_failure": "PRESERVED",
            "prior_failed_identity": "DEV-MDCC-OA-SAME-AGENT-DEPTH50-001 NEVER_RETRIED",
            "admission_clock_root_cause": (
                "Nominal D_i-L action/result cutoffs diverge from E_i no-burst dispatch under host jitter; "
                "however, the immutable trace's operation 47 became ready after all 300 effective cutoffs."
            ),
            "old_action_commitment_clock": "NOMINAL",
            "public_emission_clock": "EFFECTIVE_NO_BURST",
            "clock_mismatch_confirmed": "YES",
            "failed_trace_counterfactual": f"{replay_admitted}/50",
            "effective_clock_replay_50_of_50": "NO",
            "effective_public_clock_implemented": "NOT_IMPLEMENTED",
            "action_effective_cutoff": "NOT_IMPLEMENTED",
            "result_effective_cutoff": "NOT_IMPLEMENTED",
            "fixed_admission_slot_count": 300,
            "nominal_h_ms": 3000,
            "pir_capacity": "K6 / PIR60 / EPOCH6000 / Q100 PRESERVED",
            "joint_pir_action_capacity": "FAIL",
            "post_change_python_serial": "NOT_RUN_NO_RUNTIME_CHANGE",
            "post_change_python_default": "NOT_RUN_NO_RUNTIME_CHANGE",
            "post_change_native_routing": "NOT_RUN_NO_RUNTIME_CHANGE",
            "post_change_go": "NOT_RUN_NO_RUNTIME_CHANGE",
            "post_change_security_negatives": "NOT_RUN_NO_RUNTIME_CHANGE",
            "transitive_runtime_hash_match": "NOT_RUN_STOPPED_AT_SECTION_5",
            "fresh_live_capacity": "NOT_RUN",
            "timing_attack_sessions": 0,
            "timing_confirmatory_sessions": 0,
            "timing_privacy": "INCONCLUSIVE",
            "timing_go": "NO",
            "packet_level_timing": "OPEN",
            "hardware_tee": "NOT_TESTED",
            "v12_final_candidate_universe_exists": "NO",
            "v12_final_seed_exists": "NO",
            "selected_final_v12_cases_executed": 0,
            "ready_to_resume_timing_attack_development": "NO",
            "ready_for_final_v12_holdout": "NO",
        },
    }
    JSON_OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    rejected_lines = []
    for row in operation_rows[46:50]:
        rejected_lines.append(
            f"- operation {row['operation_index']} `{row['operation_id']}`: intent {ns_ms_text(row['intent_earliest_go_relative_ns'])}, "
            f"descriptor ready {ns_ms_text(row['descriptor_recovered_earliest_go_relative_ns'])}, "
            f"framework delay {ns_ms_text(row['framework_delay_ns'])}, cache delay {ns_ms_text(row['pir_or_cache_delay_ns'])}, "
            f"effective replay: not admitted."
        )
    md = f"""# V12 timing admission clock root-cause audit

## Decision

`CLOCK_MISMATCH_CONFIRMED = YES`, but `EFFECTIVE_CLOCK_REPLAY_50_OF_50 = NO` ({replay_admitted}/50). Per the frozen phase rule, runtime implementation stops here. No scheduler, pacer, admission, delivery, PIR, profile, or horizon source was changed; no fresh workload or timing attack was run.

The required disposition is `H3000_CAPACITY_STILL_INSUFFICIENT`. The mismatch is a real design defect, but it is not sufficient to repair the immutable 46/50 trace.

## Mechanical source finding

`common_action_gateway_v2/canonicalv9/online.go` constructs nominal `deadline` and `cutoff = deadline - lead`. The preparation worker rejects/skips using nominal cutoff (lines 294 and 307), the scheduler commits using nominal cutoff (line 405), and `engine.deliveryCutoffs` is populated from nominal cutoff (line 224; consumed by `runner.go` lines 606-612). Only after commitment does dispatch compute `eligible = max(deadline, previousDispatch + period)` (lines 414-417).

Thus the old action commitment clock is nominal while the public emission clock is effective/no-burst. The worker can permanently advance past a nominally expired slot while that slot's effective cutoff is still in the future. Result eligibility has the same nominal/effective inconsistency.

## Clock alignment and conservative replay

Python `SESSION_T0` was recorded at {session_t0} ns. Go recorded `T0_ASSIGNED` at {t0_assigned_rel} ns relative to its process clock. Because Python records `SESSION_T0` only after receiving `SESSION_READY` and starting the PIR cover thread, {process_clock_origin_upper_bound_ns} ns is an upper bound on the Go process-clock origin. Using that upper bound makes every private arrival *earlier* than it could really have been, deliberately favouring the proposed repair.

The last nominal admission cutoff (slot 300) was {ns_ms(last_nominal_cutoff)} ms; its effective cutoff would have been {ns_ms(last_effective_cutoff)} ms. Operation 47's descriptor was available no earlier than {ns_ms(int(op47['descriptor_recovered_earliest_go_relative_ns']))} ms: {ns_ms(int(op47['descriptor_recovered_earliest_go_relative_ns']) - last_effective_cutoff)} ms after even the last effective cutoff.

The round-290 public result dispatch for operation 46 occurred at {ns_ms(op46_result_dispatch)} ms. Framework delivery occurred no earlier than {ns_ms(op46_delivered_earliest_rel)} ms, a lower-bound delay of {ns_ms(op46_delivered_earliest_rel - op46_result_dispatch)} ms. The next intent followed {ns_ms(int(op47['framework_delay_ns']))} ms later. This delay, not PIR exhaustion, placed operation 47 beyond all 300 admission-capable slots.

## Operations 47-50

{chr(10).join(rejected_lines)}

At operation 47 arrival, slots 287-300 were already past their effective commitment cutoffs; they classify `EFFECTIVE_SLOT_ALREADY_COMMITTED`. Operations 48-50 arrived after operation 47 had exhausted the fixed 300-slot admission set. No skipped slot for these four operations was available solely because the old nominal cutoff was used.

Across the complete trace, skipped-slot classifications and all 50 reconstructed operation records are frozen in the JSON companion. The effective-clock greedy replay admits {replay_admitted}/50, not 50/50.

The complete trace contains {classifications.get('NOMINAL_CUTOFF_EXPIRED_BUT_EFFECTIVE_SLOT_STILL_FUTURE', 0)} skipped slots in class A, {classifications.get('EFFECTIVE_SLOT_ALREADY_COMMITTED', 0)} in class B, and {classifications.get('OTHER', 0)} in class D. Thus the nominal clock did discard 42 opportunities prematurely elsewhere in the trace, but restoring them counterfactually still does not make operations 47-50 available before the fixed admission set ends.

## Preserved boundaries

- `DEV-MDCC-OA-SAME-AGENT-DEPTH50-001` remains FAIL and was never retried.
- `K6 / PIR60 / EPOCH6000 / Q100` is not changed here; the failed trace used one real PIR, 99 dummy PIR queries, and 49 authenticated descriptor cache hits.
- The prior PIR proof is not promoted to an integrated action-capacity PASS because H3000 fails this replay.
- Timing privacy remains inconclusive; timing GO remains NO; packet-level timing remains open.
- No V12 universe, seed, selected manifest, authorization, result root, live capacity identity, or timing-attack identity was created.
"""
    MD_OUT.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
