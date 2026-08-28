from __future__ import annotations

import asyncio
import hashlib
import json
import math
import secrets
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Mapping

from src.path_oram import PathORAM


FORBIDDEN = {
    "private_state", "private_label", "permission_exists", "provenance_exists",
    "approval_needed", "is_dummy", "logical_id", "selected_agent",
}


@dataclass(frozen=True)
class StepResult:
    raw_bytes: int
    interrupted: bool = False
    proposal_ready: bool = False
    result: str = "completed"


@dataclass(frozen=True)
class LiveConfig:
    horizon: int = 5
    delta_ms: float = 5.0
    frame_bytes: int = 4096
    approval_window_ms: float = 20.0
    size_mode: str = "FIXED"  # NONE, FIXED, BUCKET
    buckets: tuple[int, ...] = (512, 1024, 2048, 4096, 8192, 16384)


class PrivateAccessPlane:
    """Existing Path-ORAM trace simulator; no new ORAM construction."""

    def __init__(self, seed: int, blocks: int = 128):
        self.oram = PathORAM(blocks, seed, 4, math.ceil(math.log2(blocks)))

    def access(self, semantic_key: str) -> Mapping[str, object]:
        block = int.from_bytes(hashlib.sha256(semantic_key.encode()).digest()[:8], "big") % self.oram.n_blocks
        _, physical = self.oram.access(block, "read")
        return physical


def serialize_frame(payload_bytes: int, mode: str, fixed: int, buckets: tuple[int, ...]) -> bytes:
    """Materialize a binary host-bound frame and return the actual bytes.

    Payload content is represented by locally generated opaque bytes. This is
    framing/length enforcement, not a new encryption construction.
    """

    raw_size = max(24, int(payload_bytes)) + 8
    if mode == "NONE":
        target = raw_size
    elif mode == "FIXED":
        if raw_size > fixed:
            raise OverflowError(f"serialized payload {raw_size} exceeds public bound {fixed}")
        target = fixed
    elif mode == "BUCKET":
        target = next((b for b in buckets if b >= raw_size), 0)
        if not target:
            raise OverflowError(f"serialized payload {raw_size} exceeds public buckets")
    else:
        raise ValueError(mode)
    # The returned object is an actual target-length byte string, rather than a
    # rewritten metadata counter. A production transport would encrypt it.
    return secrets.token_bytes(target)


async def _dummy_work() -> StepResult:
    # Safe CPU-only trusted cover. It cannot cross the external effect gate.
    hashlib.sha256(secrets.token_bytes(64)).digest()
    await asyncio.sleep(0)
    return StepResult(256)


async def _sleep_until(deadline_ns: int) -> int:
    # Windows' default asyncio timer may overshoot millisecond deadlines by a
    # full scheduler quantum. Sleep for the coarse portion, then use a short
    # (<1 ms) high-resolution spin at the trusted transport boundary.
    while True:
        remaining = deadline_ns - time.perf_counter_ns()
        if remaining <= 0:
            return time.perf_counter_ns()
        if remaining > 2_000_000:
            time.sleep((remaining - 1_800_000) / 1e9)


def assert_host_trace(trace: list[dict[str, object]]) -> None:
    encoded = json.dumps(trace, sort_keys=True)
    for name in FORBIDDEN:
        if name in encoded:
            raise AssertionError(f"private field leaked to host trace: {name}")


async def run_live(
    *,
    variant: str,
    config: LiveConfig,
    real_steps: list[Callable[[], Awaitable[StepResult]]],
    approval_work: Callable[[], Awaitable[None]],
    commit: Callable[[], Mapping[str, object]],
    seed: int,
) -> dict[str, object]:
    """Run native work inside M0--M3 transport/scheduling enforcement.

    M2 fixes structural slots. M3 additionally materializes fixed-size frames
    and enforces wall-clock round/approval deadlines. External commit remains a
    distinct trusted gate and is invoked exactly once after successful slots.
    """

    if variant not in {"M0", "M1", "M2", "M3"}:
        raise ValueError(variant)
    host: list[dict[str, object]] = []
    private: list[dict[str, object]] = []
    plane = PrivateAccessPlane(seed)
    started = time.perf_counter_ns()
    previous_observed = started
    slot_count = len(real_steps) if variant in {"M0", "M1"} else config.horizon
    if slot_count > config.horizon and variant in {"M2", "M3"}:
        return {"success": False, "overflow": True, "host_visible_trace": [], "private_audit": []}

    step_index = 0
    proposal_ready = False
    overflow_count = 0
    total_wait_ns = 0
    total_work_ns = 0
    dummy_slots = 0
    oram_accesses = 0

    for round_index in range(1, slot_count + 1):
        work_started = time.perf_counter_ns()
        if step_index < len(real_steps):
            result = await real_steps[step_index]()
            step_index += 1
            real = True
        else:
            result = await _dummy_work()
            real = False
            dummy_slots += 1
        proposal_ready = proposal_ready or result.proposal_ready

        physical_events: list[dict[str, object]] = []
        if variant != "M0":
            for access_index in range(3):
                physical = plane.access(f"slot:{round_index}:{access_index}:{'r' if real else 'c'}")
                physical_events.append({
                    "sequence": len(host) + len(physical_events) + 1,
                    "round": round_index,
                    "operation_class": "ORAM_PATH_ACCESS",
                    "physical_leaf": int(physical["leaf"]),
                    "path_bucket_count": int(physical["buckets_touched"]),
                    "serialized_bytes": 8192,
                })
                oram_accesses += 1

        frame_mode = config.size_mode if variant == "M3" else "NONE"
        frame = serialize_frame(result.raw_bytes, frame_mode, config.frame_bytes, config.buckets)
        total_work_ns += time.perf_counter_ns() - work_started

        if variant == "M3":
            epoch_offset = config.approval_window_ms if round_index > 1 else 0.0
            deadline = started + int((round_index * config.delta_ms + epoch_offset) * 1e6)
            before_wait = time.perf_counter_ns()
            observed = await _sleep_until(deadline)
            total_wait_ns += max(0, observed - before_wait)
            if before_wait > deadline:
                overflow_count += 1
        else:
            observed = time.perf_counter_ns()

        for event in physical_events:
            event["observed_offset_ms"] = (observed - started) / 1e6
            host.append(event)
        host.append({
            "sequence": len(host) + 1,
            "round": round_index,
            "operation_class": "MEDIATION_SLOT" if variant != "M0" else ("APPROVAL_INTERRUPTION" if result.interrupted else "RUNTIME_INVOCATION"),
            "serialized_bytes": len(frame),
            "observed_offset_ms": (observed - started) / 1e6,
            "inter_event_ms": (observed - previous_observed) / 1e6,
        })
        previous_observed = observed
        private.append({"round": round_index, "real": real, "raw_bytes": result.raw_bytes})

        # The first native step establishes whether local approval work is
        # required. Both M3 branches enter the same public epoch.
        if round_index == 1:
            approval_started = time.perf_counter_ns()
            await approval_work()
            if variant == "M3":
                epoch_deadline = approval_started + int(config.approval_window_ms * 1e6)
                before_wait = time.perf_counter_ns()
                observed = await _sleep_until(epoch_deadline)
                total_wait_ns += max(0, observed - before_wait)
                if before_wait > epoch_deadline:
                    overflow_count += 1
                epoch_frame = serialize_frame(192, config.size_mode, config.frame_bytes, config.buckets)
                host.append({
                    "sequence": len(host) + 1,
                    "round": round_index,
                    "operation_class": "APPROVAL_EPOCH",
                    "serialized_bytes": len(epoch_frame),
                    "observed_offset_ms": (observed - started) / 1e6,
                    "inter_event_ms": (observed - previous_observed) / 1e6,
                })
                previous_observed = observed
            elif variant == "M0" and result.interrupted:
                observed = time.perf_counter_ns()
                host.append({
                    "sequence": len(host) + 1,
                    "round": round_index,
                    "operation_class": "LOCAL_APPROVAL_DECISION",
                    "serialized_bytes": 192,
                    "observed_offset_ms": (observed - started) / 1e6,
                    "inter_event_ms": (observed - previous_observed) / 1e6,
                })
                previous_observed = observed

    if not proposal_ready:
        raise AssertionError("native mediation completed without an effect proposal")
    effect = dict(commit())
    observed = time.perf_counter_ns()
    commit_frame = serialize_frame(256, config.size_mode if variant == "M3" else "NONE", config.frame_bytes, config.buckets)
    host.append({
        "sequence": len(host) + 1,
        "round": slot_count,
        "operation_class": "PUBLIC_COMMIT",
        "serialized_bytes": len(commit_frame),
        "observed_offset_ms": (observed - started) / 1e6,
        "inter_event_ms": (observed - previous_observed) / 1e6,
    })
    assert_host_trace(host)
    elapsed_ns = time.perf_counter_ns() - started
    return {
        "success": True,
        "overflow": False,
        "host_visible_trace": host,
        "private_audit": private,
        "effect": effect,
        "effect_count": 1,
        "dummy_external_effects": 0,
        "oram_accesses": oram_accesses,
        "dummy_slots": dummy_slots,
        "latency_ms": elapsed_ns / 1e6,
        "wait_fraction": total_wait_ns / elapsed_ns if elapsed_ns else 0.0,
        "work_fraction": total_work_ns / elapsed_ns if elapsed_ns else 0.0,
        "deadline_overflows": overflow_count,
    }
