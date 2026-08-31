from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ResolutionArrival:
    request_id: str
    agent_id: int
    arrival_ms: float


@dataclass(frozen=True)
class CapacityContract:
    admission_horizon_ms: int = 3000
    pir_initial_lead_ms: int = 25
    pir_period_ms: int = 60
    pir_public_epoch_ms: int = 6000
    pir_query_completion_bound_ms: int = 50
    preparation_margin_ms: int = 1
    maximum_real_agent_resolutions: int = 6

    @property
    def query_count(self) -> int:
        return self.pir_public_epoch_ms // self.pir_period_ms

    @property
    def latest_real_arrival_ms(self) -> int:
        return (
            self.admission_horizon_ms
            - self.maximum_real_agent_resolutions * self.pir_period_ms
            - self.pir_query_completion_bound_ms
            - self.preparation_margin_ms
        )

    def validate(self) -> "CapacityContract":
        if self.pir_public_epoch_ms % self.pir_period_ms:
            raise ValueError("public PIR epoch must contain an integral opportunity count")
        if self.maximum_real_agent_resolutions != 6:
            raise ValueError("current framework scope has exactly six resolvable descriptor identities")
        if self.latest_real_arrival_ms <= 0:
            raise ValueError("joint PIR/action capacity has no positive real-resolution arrival horizon")
        return self


def simulate_arrivals(
    arrivals: Iterable[ResolutionArrival],
    contract: CapacityContract = CapacityContract(),
) -> dict[str, object]:
    """Deterministically schedule cache misses on the fixed public PIR epoch."""

    contract.validate()
    ordered = sorted(arrivals, key=lambda item: (item.arrival_ms, item.request_id))
    cache: set[int] = set()
    misses: list[ResolutionArrival] = []
    cache_hits: list[str] = []
    for item in ordered:
        if item.agent_id in cache:
            cache_hits.append(item.request_id)
            continue
        cache.add(item.agent_id)
        misses.append(item)
    failures: list[str] = []
    if len(cache) > contract.maximum_real_agent_resolutions:
        failures.append("MAX_REAL_AGENT_RESOLUTIONS_EXCEEDED")
    if any(item.arrival_ms > contract.latest_real_arrival_ms for item in misses):
        failures.append("PIR_REAL_RESOLUTION_ARRIVAL_CUTOFF_EXCEEDED")

    opportunities = [
        contract.pir_initial_lead_ms + ordinal * contract.pir_period_ms
        for ordinal in range(contract.query_count)
    ]
    assignments: list[dict[str, object]] = []
    opportunity_index = 0
    max_queue = 0
    for item in misses:
        while opportunity_index < len(opportunities) and opportunities[opportunity_index] < item.arrival_ms:
            opportunity_index += 1
        if opportunity_index >= len(opportunities):
            failures.append("FIXED_PIR_EPOCH_EXHAUSTED")
            break
        start_ms = opportunities[opportunity_index]
        completion_ms = start_ms + contract.pir_query_completion_bound_ms
        queued = sum(1 for other in misses if other.arrival_ms <= start_ms) - len(assignments)
        max_queue = max(max_queue, queued)
        assignments.append(
            {
                "request_id": item.request_id,
                "agent_id": item.agent_id,
                "arrival_ms": item.arrival_ms,
                "opportunity_ordinal": opportunity_index,
                "start_ms": start_ms,
                "completion_ms": completion_ms,
                "resolution_delay_ms": completion_ms - item.arrival_ms,
            }
        )
        opportunity_index += 1
    if assignments and max(float(item["completion_ms"]) for item in assignments) + contract.preparation_margin_ms >= contract.admission_horizon_ms:
        failures.append("ACTION_PREPARATION_NOT_STRICTLY_BEFORE_H")
    return {
        "passed": not failures,
        "failures": failures,
        "K": contract.maximum_real_agent_resolutions,
        "Q": contract.query_count,
        "pir_period_ms": contract.pir_period_ms,
        "pir_public_epoch_ms": contract.pir_public_epoch_ms,
        "latest_real_arrival_ms": contract.latest_real_arrival_ms,
        "real_resolution_count": len(misses),
        "cache_hit_count": len(cache_hits),
        "cache_hit_request_ids": cache_hits,
        "maximum_queue_occupancy": max_queue,
        "worst_case_modeled_resolution_delay_ms": max(
            (float(item["resolution_delay_ms"]) for item in assignments), default=0.0
        ),
        "assignments": assignments,
    }


def adversarial_in_scope_traces(contract: CapacityContract = CapacityContract()) -> dict[str, list[ResolutionArrival]]:
    contract.validate()
    supported_agent_ids = (10, 11, 12, 13, 20, 21)
    k = len(supported_agent_ids)
    immediate = [ResolutionArrival(f"immediate-{i}", agent_id, 0.0) for i, agent_id in enumerate(supported_agent_ids)]
    delayed = [ResolutionArrival("delayed-boundary", 10, float(contract.latest_real_arrival_ms))]
    after_opportunity = [
        ResolutionArrival(f"after-opportunity-{i}", agent_id, contract.pir_initial_lead_ms + 0.001)
        for i, agent_id in enumerate(supported_agent_ids)
    ]
    bursts = [
        *[ResolutionArrival(f"burst-a-{i}", agent_id, 1000.0) for i, agent_id in enumerate(supported_agent_ids[:3])],
        *[ResolutionArrival(f"burst-b-{i}", agent_id, 2000.0) for i, agent_id in enumerate(supported_agent_ids[3:])],
    ]
    mixed_ids = (10, 10, 21, 21, 11, 10, 12, 13, 20)
    cache_mixed = [ResolutionArrival(f"cache-{i}", agent_id, 100.0 + i) for i, agent_id in enumerate(mixed_ids)]

    causal: list[ResolutionArrival] = []
    next_arrival = 0.0
    for i in range(k):
        value = ResolutionArrival(f"causal-{i}", supported_agent_ids[i], next_arrival)
        causal.append(value)
        result = simulate_arrivals(causal, contract)
        assignment = result["assignments"][-1]
        next_arrival = float(assignment["completion_ms"]) + 60.0
    return {
        "all_K_immediate": immediate,
        "first_near_latest_supported_boundary": delayed,
        "one_after_each_prior_resolution_result": causal,
        "arrivals_immediately_after_cover_opportunity": after_opportunity,
        "multiple_pending_bursts": bursts,
        "cache_hits_mixed_with_new_resolutions": cache_mixed,
    }


def run_capacity_suite(contract: CapacityContract = CapacityContract()) -> dict[str, object]:
    results = {
        name: simulate_arrivals(arrivals, contract)
        for name, arrivals in adversarial_in_scope_traces(contract).items()
    }
    return {
        "schema": "AgentTool.V12PIRCausalCapacityModelResult/1",
        "contract": {
            "K": contract.maximum_real_agent_resolutions,
            "Q": contract.query_count,
            "pir_period_ms": contract.pir_period_ms,
            "pir_public_epoch_ms": contract.pir_public_epoch_ms,
            "pir_initial_lead_ms": contract.pir_initial_lead_ms,
            "pir_query_completion_bound_ms": contract.pir_query_completion_bound_ms,
            "latest_real_resolution_arrival_ms": contract.latest_real_arrival_ms,
            "admission_horizon_ms": contract.admission_horizon_ms,
        },
        "traces": results,
        "passed": all(bool(value["passed"]) for value in results.values()),
        "maximum_queue_occupancy": max(int(value["maximum_queue_occupancy"]) for value in results.values()),
        "worst_case_modeled_resolution_delay_ms": max(
            float(value["worst_case_modeled_resolution_delay_ms"]) for value in results.values()
        ),
    }
