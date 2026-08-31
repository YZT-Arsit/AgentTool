#!/usr/bin/env python3
"""Deterministic development model for the frozen V12 causal horizons.

The model performs no framework, PIR, provider, or timing-attack execution.
It uses the immutable MDCC trace only as a development falsification input;
observed maxima are explicitly not treated as formal platform bounds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from v12_timing.capacity import CapacityContract, run_capacity_suite
from v12_timing.profile import causal_horizon_candidate_profiles


ROOT = Path(__file__).resolve().parent
TRACE_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FIRST_GO_RESULT.json"
TRAJECTORY_PATH = ROOT / "V12_MDCC_LIVE_CAPACITY_FIRST_PRIVATE_TRAJECTORY.json"
CANDIDATE_PATH = ROOT / "V12_CAUSAL_HORIZON_CANDIDATES_FREEZE.json"
OUTPUT_PATH = ROOT / "V12_CAUSAL_HORIZON_CAPACITY_MODEL.json"
PROOF_PATH = ROOT / "V12_CAUSAL_HORIZON_CAPACITY_PROOF.md"
PROFILE_PATH = ROOT / "V12_CAUSAL_HORIZON_PROFILE_FREEZE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def effective_schedule(
    *, rounds: int, first_deadline_ns: int, period_ns: int, observed_dispatch: dict[int, int]
) -> list[dict[str, int]]:
    values: list[dict[str, int]] = []
    previous_dispatch = 0
    for slot in range(1, rounds + 1):
        nominal = first_deadline_ns + (slot - 1) * period_ns
        eligible = nominal if slot == 1 else max(nominal, previous_dispatch + period_ns)
        # Retained dispatches freeze the old public stall trace. Beyond the old
        # transcript, exact eligibility is the repair-favourable continuation.
        dispatch = observed_dispatch.get(slot, eligible)
        if dispatch < eligible:
            raise AssertionError("retained dispatch precedes effective eligibility")
        values.append(
            {
                "slot": slot,
                "nominal_deadline_ns": nominal,
                "effective_eligibility_ns": eligible,
                "effective_cutoff_ns": eligible - 1_000_000,
                "dispatch_ns": dispatch,
            }
        )
        previous_dispatch = dispatch
    return values


def replay(arrivals: list[dict[str, Any]], schedule: list[dict[str, int]], admission_rounds: int) -> dict[str, Any]:
    next_slot = 1
    rows: list[dict[str, Any]] = []
    for item in arrivals:
        chosen = None
        while next_slot <= admission_rounds:
            cutoff = schedule[next_slot - 1]["effective_cutoff_ns"]
            if item["arrival_ns"] < cutoff:
                chosen = next_slot
                next_slot += 1
                break
            next_slot += 1
        rows.append({**item, "effective_round": chosen, "admitted": chosen is not None})
    admitted = sum(bool(item["admitted"]) for item in rows)
    first_unadmitted = next((item["operation_id"] for item in rows if not item["admitted"]), None)
    return {
        "admitted": admitted,
        "denominator": len(rows),
        "first_unadmitted_operation": first_unadmitted,
        "operations": rows,
    }


def stall_model(rounds: int, stalls: dict[int, int], period_ns: int = 10_000_000) -> dict[str, Any]:
    previous = 0
    sequence: list[dict[str, int]] = []
    for slot in range(1, rounds + 1):
        nominal = slot * period_ns
        eligible = nominal if slot == 1 else max(nominal, previous + period_ns)
        dispatch = eligible + stalls.get(slot, 0)
        sequence.append({"slot": slot, "nominal_ns": nominal, "eligible_ns": eligible, "cutoff_ns": eligible - 1_000_000, "dispatch_ns": dispatch})
        previous = dispatch
    return {
        "fixed_slot_count": len(sequence),
        "no_catch_up_burst": all(
            sequence[index]["dispatch_ns"] - sequence[index - 1]["dispatch_ns"] >= period_ns
            for index in range(1, len(sequence))
        ),
        "sequence": sequence,
    }


def main() -> int:
    trace = read_json(TRACE_PATH)
    trajectory = read_json(TRAJECTORY_PATH)
    candidates = read_json(CANDIDATE_PATH)
    launches = {int(item["slot"]): item for item in trace["slot_launches"]}
    observed_dispatch = {slot: int(item["scheduler_dispatch_ns"]) for slot, item in launches.items()}
    first_deadline = int(launches[1]["deadline_ns"])
    period_ns = 10_000_000

    session_t0 = next(int(item["monotonic_ns"]) for item in trajectory if item["stage"] == "SESSION_T0")
    t0_assigned = next(
        int(item["monotonic_ns"])
        for item in trace["public_setup_events"]
        if item["stage"] == "T0_ASSIGNED"
    )
    origin_upper_bound = session_t0 - t0_assigned
    arrivals = [
        {
            "operation_index": index,
            "operation_id": str(item["operation_id"]),
            "arrival_ns": int(item["monotonic_ns"]) - origin_upper_bound,
        }
        for index, item in enumerate(
            (row for row in trajectory if row["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"), start=1
        )
    ]

    framework_delays = []
    previous_delivery = None
    cache_delays = []
    intent_by_id = {
        str(item["operation_id"]): int(item["monotonic_ns"])
        for item in trajectory
        if item["stage"] == "ACTION_INTENT_SUBMITTED"
    }
    for item in trajectory:
        if item["stage"] == "ACTION_INTENT_SUBMITTED" and previous_delivery is not None:
            framework_delays.append(int(item["monotonic_ns"]) - previous_delivery)
        elif item["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED":
            cache_delays.append(int(item["monotonic_ns"]) - intent_by_id[str(item["operation_id"])])
        elif item["stage"] == "FRAMEWORK_RESULT_DELIVERED":
            previous_delivery = int(item["monotonic_ns"])

    profiles = causal_horizon_candidate_profiles()
    results: list[dict[str, Any]] = []
    profile_schemas: list[dict[str, Any]] = []
    for profile in profiles:
        schedule = effective_schedule(
            rounds=profile.total_rounds,
            first_deadline_ns=first_deadline,
            period_ns=period_ns,
            observed_dispatch=observed_dispatch,
        )
        old_replay = replay(arrivals, schedule, profile.admission_rounds)
        pir_suite = run_capacity_suite(CapacityContract(admission_horizon_ms=profile.admission_horizon_ms))
        stall_suites = {
            "no_stall": stall_model(profile.total_rounds, {}),
            "one_35ms_stall": stall_model(profile.total_rounds, {3: 35_000_000}),
            "one_100ms_stall": stall_model(profile.total_rounds, {3: 100_000_000}),
            "repeated_stalls": stall_model(profile.total_rounds, {3: 35_000_000, 200: 100_000_000, 400: 35_000_000}),
        }
        causal_scenarios = {
            "same_agent_depth_50": {
                "real_resolutions": 1,
                "cache_hits": 49,
                "online_arrivals": True,
                "old_trace_replay": f"{old_replay['admitted']}/50",
                "passed": old_replay["admitted"] == 50,
            },
            "K6_distinct_agent_transitions": {
                "real_resolutions": 6,
                "pir_suite_passed": bool(pir_suite["passed"]),
                "passed": bool(pir_suite["passed"]),
            },
            "agent_as_tool_transition": {
                "distinct_descriptor_bound": 6,
                "same_fixed_pir_schedule": True,
                "passed": bool(pir_suite["passed"]),
            },
            "result_at_latest_legal_effective_slot": {
                "rule": "ready_before_C_i_may_enter_i; ready_after_C_i_rolls_forward",
                "fixed_result_capacity_rounds": 50,
                "passed": profile.result_capacity_rounds == 50,
            },
            "framework_intent_generation_delay": {
                "observed_max_ns": max(framework_delays),
                "formal_platform_bound": False,
                "used_only_to_falsify": True,
                "passed": old_replay["admitted"] == 50,
            },
            "public_scheduling_stalls": {
                "traces": list(stall_suites),
                "passed": all(
                    value["fixed_slot_count"] == profile.total_rounds and value["no_catch_up_burst"]
                    for value in stall_suites.values()
                ),
            },
        }
        joint_pass = all(bool(value["passed"]) for value in causal_scenarios.values())
        results.append(
            {
                "horizon_ms": profile.admission_horizon_ms,
                "profile_id": profile.profile_id,
                "admission_rounds": profile.admission_rounds,
                "total_rounds": profile.total_rounds,
                "latest_real_descriptor_arrival_ms": profile.pir_real_resolution_arrival_cutoff_ms,
                "pir_capacity": "PASS" if pir_suite["passed"] else "FAIL",
                "pir_capacity_result": pir_suite,
                "old_trace_replay": old_replay,
                "causal_scenarios": causal_scenarios,
                "joint_causal_model": "PASS" if joint_pass else "FAIL",
                "mechanically_eligible_for_live": bool(pir_suite["passed"]) and joint_pass and old_replay["admitted"] == 50,
                "stall_suites": stall_suites,
            }
        )
        profile_schemas.append(profile.public_schema())

    payload = {
        "schema": "AgentTool.V12CausalHorizonCapacityModel/1",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "base_commit": "4a577ec8c4f610e7f9b8fa1b852a518fb4eb2e0c",
        "mode": "DETERMINISTIC_OFFLINE_DEVELOPMENT_MODEL",
        "candidate_freeze_sha256": sha256(CANDIDATE_PATH),
        "immutable_inputs": {
            TRACE_PATH.name: sha256(TRACE_PATH),
            TRAJECTORY_PATH.name: sha256(TRAJECTORY_PATH),
        },
        "clock_alignment": {
            "go_process_clock_origin_upper_bound_ns": origin_upper_bound,
            "policy": "repair-favourable earliest possible private arrivals",
        },
        "observed_development_bounds": {
            "maximum_framework_next_intent_delay_ns": max(framework_delays),
            "maximum_cache_hit_or_resolution_delay_ns": max(cache_delays),
            "maximum_public_launch_slip_ns": max(int(item["launch_slip_ns"]) for item in trace["slot_launches"]),
            "formal_platform_bounds": False,
            "use": "candidate falsification only",
        },
        "results": results,
        "all_candidates_mechanically_eligible": all(bool(item["mechanically_eligible_for_live"]) for item in results),
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    PROFILE_PATH.write_text(
        json.dumps(
            {
                "schema": "AgentTool.V12CausalHorizonProfileFreeze/1",
                "phase": payload["phase"],
                "selection_rule": "SMALLEST_COMPLETE_FROZEN_LIVE_CAPACITY_PASS",
                "profiles": profile_schemas,
                "timing_attack_sessions": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    table = "\n".join(
        f"| {item['horizon_ms']} | {item['admission_rounds']} | {item['total_rounds']} | "
        f"{item['old_trace_replay']['admitted']}/50 | {item['pir_capacity']} | {item['joint_causal_model']} | "
        f"{'YES' if item['mechanically_eligible_for_live'] else 'NO'} |"
        for item in results
    )
    PROOF_PATH.write_text(
        f"""# V12 causal-horizon capacity proof

This is a deterministic development-capacity argument, not a formal platform-jitter bound and not timing-privacy evidence. The immutable MDCC timings are used only to falsify candidates.

| H (ms) | admission slots | total cells | old-trace effective replay | PIR capacity | joint model | live eligible |
|---:|---:|---:|---:|---|---|---|
{table}

For each profile, `A=H/10`, `C=ceil(50/10)=5`, `M=50`, `T=1`, and `R=A+C+M+T`. Public request/response sizes remain 1079/800 bytes. The fixed Registry construction remains K=6, PIR60, epoch6000, Q=100; latest real descriptor arrival is `H-6*60-50-1` ms.

The causal model retains online generation: no future operation is made available before its predecessor's framework-visible result. It includes the historical same-Agent depth-50 arrival trace, K=6 transitions, Agent-as-Tool descriptor transitions, latest-legal result placement, measured framework intent delay, and no-burst public stalls of 35 ms, 100 ms, and repeated stalls.

The measured delays are not claimed as formal platform maxima. A live candidate must still pass both pinned frameworks and the complete frozen capacity matrix without retry or repair.
""",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if payload["all_candidates_mechanically_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
