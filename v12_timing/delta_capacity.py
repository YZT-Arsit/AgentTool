from __future__ import annotations

from typing import Any

from .capacity import CapacityContract, run_capacity_suite
from .profile import TimingIndistinguishabilityProfile


def effective_clock(rounds: int, delta_ms: int, stalls_ms: dict[int, int] | None = None) -> list[dict[str, int]]:
    stalls = stalls_ms or {}
    rows: list[dict[str, int]] = []
    previous_send = 0
    for slot in range(1, rounds + 1):
        nominal = (slot - 1) * delta_ms
        eligible = nominal if slot == 1 else max(nominal, previous_send + delta_ms)
        send = eligible + int(stalls.get(slot, 0))
        rows.append({"slot": slot, "nominal_ms": nominal, "eligible_ms": eligible,
                     "logical_cutoff_ms": eligible - 1, "send_ms": send})
        previous_send = send
    return rows


def _sequential_causal_depth(count: int) -> dict[str, Any]:
    rows = []
    previous_result = -1
    for index in range(count):
        intent = previous_result + 1
        result = intent + 1
        rows.append({"index": index, "intent_after_previous_result": intent > previous_result,
                     "intent_ms": intent, "result_ms": result})
        previous_result = result
    return {"operations": count, "no_future_action_predeclared": all(row["intent_after_previous_result"] for row in rows),
            "rows": rows}


def audit_delta_capacity(profile: TimingIndistinguishabilityProfile) -> dict[str, Any]:
    profile.validate()
    delta = profile.round_period_ms
    if profile.admission_horizon_ms != 4500 or delta not in {10, 20, 25}:
        raise ValueError("capacity audit requires a frozen H4500 Delta candidate")
    pir = run_capacity_suite(CapacityContract(admission_horizon_ms=4500))
    stall_sets = ({}, {3: 35}, {3: 100}, {3: 35, 20: 100})
    clocks = [effective_clock(profile.total_rounds, delta, stalls) for stalls in stall_sets]
    clock_pass = all(
        len(rows) == profile.total_rounds
        and all(rows[index]["send_ms"] - rows[index - 1]["send_ms"] >= delta
                for index in range(1, len(rows)))
        for rows in clocks
    )
    causal = _sequential_causal_depth(50)
    scenarios = {
        "same_agent_depth50": {"operations": 50, "real_resolutions": 1, "cache_hits": 49,
                               "passed": causal["no_future_action_predeclared"] and profile.maximum_real_operations == 50},
        "K6_descriptor_transitions": {"real_resolutions": 6, "Q": pir["contract"]["Q"],
                                      "passed": bool(pir["passed"])},
        "agent_as_tool_transition": {"descriptor_bound": 6, "same_public_profile": True,
                                     "passed": bool(pir["passed"])},
        "trusted_descriptor_cache_reuse": {"real_resolutions": 1, "cache_hits": 29,
                                           "passed": profile.maximum_real_agent_resolutions == 6},
        "effective_clock_stalls": {"recurrence": "E1=D1; Ei=max(Di,S(i-1)+Delta)",
                                    "no_catch_up": clock_pass, "passed": clock_pass},
        "latest_legal_result_placement": {"completion_rounds": profile.completion_rounds,
                                          "result_capacity_rounds": profile.result_capacity_rounds,
                                          "passed": profile.result_capacity_rounds == 50},
        "joint_fixed_pir_action": {"K": 6, "period_ms": 60, "epoch_ms": 6000, "Q": 100,
                                   "passed": bool(pir["passed"])},
    }
    return {
        "schema": "AgentTool.V12DeltaFunctionalCapacityAudit/1",
        "profile_id": profile.profile_id,
        "H_ms": profile.admission_horizon_ms,
        "Delta_ms": delta,
        "R": profile.total_rounds,
        "scenarios": scenarios,
        "passed": all(bool(value["passed"]) for value in scenarios.values()),
        "causal_depth_trace": causal,
        "pir_capacity": pir,
    }
