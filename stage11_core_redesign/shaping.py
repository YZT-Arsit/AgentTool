from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Mapping


FORBIDDEN_TRACE_FIELDS = {"is_dummy", "approval_needed", "private_state", "selected_agent", "semantic_key"}


@dataclass(frozen=True)
class ShapedTrace:
    host_visible: tuple[Mapping[str, object], ...]
    private_audit: tuple[Mapping[str, object], ...]
    effect_count: int
    dummy_external_effects: int
    success: bool
    cadence_ms: float
    size_bucket_bytes: int
    approval_window_ms: float


def _bucket(value: int, bucket_bytes: int) -> int:
    return max(bucket_bytes, math.ceil(value / bucket_bytes) * bucket_bytes)


def shape_bounded_trace(
    bounded_trace: list[dict[str, object]],
    *,
    horizon: int,
    cadence_ms: float,
    size_bucket_bytes: int,
    approval_exists: bool,
    approval_arrival_ms: float | None,
    approval_window_ms: float,
) -> ShapedTrace:
    """Add fixed size/cadence to an already bounded Stage-9/10 schedule.

    No sleep is performed: scheduled offsets are the observable contract. A
    production adapter must enforce these offsets at its transport boundary.
    """

    if horizon <= 0 or cadence_ms <= 0 or size_bucket_bytes <= 0 or approval_window_ms <= 0:
        raise ValueError("public shaping parameters must be positive")
    approval_granted = approval_exists or (
        approval_arrival_ms is not None and approval_arrival_ms <= approval_window_ms
    )
    # Same-success comparisons wait until the public approval-window boundary.
    # A missing/late approval fails closed in a separate public outcome class.
    host: list[Mapping[str, object]] = []
    for event in bounded_trace:
        round_index = int(event["round"])
        if round_index > horizon:
            raise ValueError("bounded trace exceeds public horizon")
        host.append(
            {
                "round": round_index,
                "scheduled_offset_ms": round(approval_window_ms + round_index * cadence_ms, 6),
                "destination_service": event["destination_service"],
                "operation_class": event["operation_class"],
                "request_bytes": _bucket(int(event["request_bytes"]), size_bucket_bytes),
                "response_bytes": _bucket(int(event["response_bytes"]), size_bucket_bytes),
                **({"physical_path": event["physical_path"]} if "physical_path" in event else {}),
            }
        )
    if not approval_granted:
        # Abort before effect. This execution is not compared with successful
        # traces under the same leakage label.
        host = [event for event in host if event["operation_class"] != "PUBLIC_EFFECT"]
    private = (
        {
            "approval_needed": not approval_exists,
            "real_local_prompt": not approval_exists,
            "approval_granted": approval_granted,
        },
    )
    encoded = json.dumps(host, sort_keys=True)
    for field in FORBIDDEN_TRACE_FIELDS:
        if field in encoded:
            raise AssertionError(f"private shaping field leaked explicitly: {field}")
    effects = sum(event["operation_class"] == "PUBLIC_EFFECT" for event in host)
    return ShapedTrace(
        tuple(host),
        private,
        effects,
        0,
        approval_granted,
        cadence_ms,
        size_bucket_bytes,
        approval_window_ms,
    )


def structural_signature(trace: tuple[Mapping[str, object], ...], *, include_physical: bool = False) -> tuple[tuple[object, ...], ...]:
    rows = []
    for event in trace:
        row: tuple[object, ...] = (
            event["round"],
            event["scheduled_offset_ms"],
            event["destination_service"],
            event["operation_class"],
            event["request_bytes"],
            event["response_bytes"],
        )
        if include_physical:
            row += (event.get("physical_path"),)
        rows.append(row)
    return tuple(rows)
