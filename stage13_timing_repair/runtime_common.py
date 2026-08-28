from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from stage13_timing_repair.egress import EgressEpisode, PersistentEgressShaper


FORBIDDEN = {"branch", "family", "private_state", "permission_exists", "provenance_exists",
             "is_dummy", "real_internal", "private_label", "logical_id"}


@dataclass(frozen=True)
class WorkResult:
    serialized_bytes: int
    proposal_ready: bool = False
    interrupted: bool = False


async def _wait_start(target_ns: int) -> None:
    while True:
        remaining = target_ns - time.perf_counter_ns()
        if remaining <= 0:
            return
        if remaining > 2_000_000:
            await asyncio.sleep((remaining - 1_000_000) / 1e9)
        else:
            await asyncio.sleep(0)


async def run_boundary_episode(
    *, shaper: PersistentEgressShaper, mode: str, horizon: int, delta_ms: float,
    frame_bytes: int, steps: list[Callable[[], Awaitable[WorkResult]]],
    after_step: Callable[[WorkResult], Awaitable[None]], intended_effect: dict[str, str],
) -> dict[str, Any]:
    session = shaper.start(mode, horizon, delta_ms, frame_bytes)
    private_events: list[dict[str, Any]] = []
    proposal_ready = False
    await _wait_start(session.start_ns)
    for index, step in enumerate(steps, 1):
        t0 = time.perf_counter_ns()
        value = await step()
        t1 = time.perf_counter_ns()
        await after_step(value)
        proposal_ready = proposal_ready or value.proposal_ready
        t2 = session.enqueue()
        private_events.append({"work_index": index, "t0": t0, "t1": t1, "t2": t2,
                               "raw_serialized_bytes": value.serialized_bytes,
                               "interrupted": value.interrupted})
    proposal_t = session.proposal() if proposal_ready else 0
    done_t = session.done()
    transport = await asyncio.to_thread(session.wait)
    success = bool(transport["final_real"] and transport["effect_count"] == 1)
    observer=[]
    for slot in transport["observer_slots"]:
        receiver_offset=(int(slot["t7"])-session.start_ns)/1e6
        observer.append({"slot":int(slot["slot"]),"operation_class":"FIXED_EGRESS_ENVELOPE",
            "receiver_bytes":int(slot["receiver_bytes"]),"scheduled_offset_ms":int(slot["slot"])*delta_ms,
            "release_offset_ms":(int(slot["t4"])-session.start_ns)/1e6,
            "send_offset_ms":(int(slot["t6"])-session.start_ns)/1e6,
            "arrival_offset_ms":receiver_offset,"receiver_start_offset_ms":(int(slot["t8"])-session.start_ns)/1e6,
            "release_slip_us":int(slot["release_slip_ns"])/1000,
            "commit_offset_ms":((int(slot["t9"])-session.start_ns)/1e6) if int(slot["t9"]) else 0.0,
            "oram_physical_leaves":list(slot["oram_physical_leaves"]),"oram_access_count":3})
    encoded=json.dumps(observer,sort_keys=True)
    if any(name in encoded for name in FORBIDDEN): raise AssertionError("private field in observer trace")
    return {"success":success,"overflow":not success,"host_visible_trace":observer,
        "private_instrumentation":private_events,"proposal_queue_time_ns":proposal_t,"done_time_ns":done_t,
        "effect":intended_effect if success else None,"effect_count":int(transport["effect_count"]),
        "dummy_external_effects":0,"private_slot_occupancy":transport["private_slot_occupancy"],
        "worker_done_by_epoch_end":transport["worker_done_by_epoch_end"],
        "latency_ms":max((row["commit_offset_ms"] or row["arrival_offset_ms"]) for row in observer),
        "deadline_miss_rate":sum(row["release_slip_us"] > 100 for row in observer)/horizon,
        "mean_release_slip_us":sum(row["release_slip_us"] for row in observer)/horizon}
