from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from canonical_v9.runner import descriptor
from v11_full_scope.frameworks import native_implementation
from v11_full_scope.models import V11ActionCase, V11ActionOutcome
from v11_online.frameworks import run_online_framework_workflow

from .isolated_tasks import PrimaryTimingWorkload
from .projection import registry_timing_projection, relay_timing_projection


SHORT_NS = 300_000
LONG_NS = 4_000_000


def _controlled_delay_ns(workload: PrimaryTimingWorkload, case: V11ActionCase, index: int) -> int:
    label = workload.label
    if workload.task_id == "T6":
        return SHORT_NS if case.logical_action_name.endswith("a") else LONG_NS
    if workload.task_id == "T4" and label == 1:
        return SHORT_NS + index * 350_000
    if workload.task_id == "T5":
        return LONG_NS if "rare" in case.logical_action_name else SHORT_NS
    return SHORT_NS if label == 0 else LONG_NS


def _busy_wait(delay_ns: int) -> None:
    target = time.perf_counter_ns() + delay_ns
    while time.perf_counter_ns() < target:
        pass


@dataclass
class _UnshapedRecorder:
    workload: PrimaryTimingWorkload
    relay_rows: list[dict[str, Any]] = field(default_factory=list)
    registry_rows: list[dict[str, Any]] = field(default_factory=list)
    resolved_agents: set[int] = field(default_factory=set)
    call_index: int = 0

    def execute(self, case: V11ActionCase, arguments: dict[str, Any]) -> V11ActionOutcome:
        index = self.call_index
        self.call_index += 1
        request_ns = time.perf_counter_ns()
        if case.agent_id not in self.resolved_agents:
            query_ns = time.perf_counter_ns()
            recovered = descriptor(case.agent_id)
            if recovered.agent_id != case.agent_id:
                raise AssertionError("unshaped control resolved the wrong public development descriptor")
            _busy_wait(_controlled_delay_ns(self.workload, case, index))
            ready_ns = time.perf_counter_ns()
            self.registry_rows.append(
                {
                    "ordinal": len(self.registry_rows),
                    "query_bytes": 0,
                    "query_rows": 1000,
                    "query_cols": 1,
                    "answer_bytes": 0,
                    "executor": "DIRECT_AUTHENTICATED_REGISTRY_CONTROL",
                    "request_kind": "REAL_RESOLUTION_ONLY_NO_COVER",
                    "request_arrival_ns": query_ns,
                    "answer_ready_ns": ready_ns,
                }
            )
            self.resolved_agents.add(case.agent_id)
        _busy_wait(_controlled_delay_ns(self.workload, case, index))
        outcome = native_implementation(case, arguments)
        response_ns = time.perf_counter_ns()
        self.relay_rows.append(
            {
                "profile_id": "UNPROTECTED-DIRECT-TIMING-CONTROL-V2",
                "session": 1,
                "round": index + 1,
                "request_length": 0,
                "response_length": 0,
                "relay_endpoint": "DIRECT_UNSHAPED_CONTROL",
                "gateway_endpoint": "DIRECT_UNSHAPED_CONTROL",
                "request_observed_ns": request_ns,
                "response_observed_ns": response_ns,
                "client_http_version": "DIRECT",
                "gateway_http_version": "DIRECT",
            }
        )
        return outcome


def run_unprotected_positive_control(workload: PrimaryTimingWorkload) -> dict[str, Any]:
    recorder = _UnshapedRecorder(workload)
    native = run_online_framework_workflow(
        workload.framework,
        workload.workflow,
        list(workload.cases),
        recorder.execute,
    )
    relay = relay_timing_projection({"public_relay_events": recorder.relay_rows})
    registry = registry_timing_projection(
        recorder.registry_rows,
        profile_id="UNPROTECTED-DIRECT-REGISTRY-CONTROL-V2",
        pir_period_ms=0,
        opportunities=len(recorder.registry_rows),
    )
    return {
        "identity": workload.identity,
        "task_id": workload.task_id,
        "framework": workload.framework,
        "label": workload.label,
        "block": workload.block,
        "functional": len(native["projection"]["trajectory"]) == len(workload.cases),
        "relay_projection": relay,
        "registry_projection": registry,
        "real_resolution_count": len(recorder.registry_rows),
        "action_count": len(recorder.relay_rows),
        "control_path": "PINNED_NATIVE_FRAMEWORK_DIRECT_UNSHAPED_WITH_REAL_RESOLUTION_ONLY",
    }
