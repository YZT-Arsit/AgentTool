from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .projection import RELAY_DUPLEX_TIMING_KEYS, timing_feature_vector

FEATURE_FAMILY_ORDER = (
    "A",
    "B",
    "C",
    "D",
    "AB",
    "BC",
    "CD",
    "REQUEST_SIDE",
    "RESPONSE_SIDE",
    "ALL",
)

FEATURE_FAMILY_KEYS = {
    "A": RELAY_DUPLEX_TIMING_KEYS[0:2],
    "B": RELAY_DUPLEX_TIMING_KEYS[2:4],
    "C": RELAY_DUPLEX_TIMING_KEYS[4:6],
    "D": RELAY_DUPLEX_TIMING_KEYS[6:8],
    "AB": RELAY_DUPLEX_TIMING_KEYS[8:9],
    "BC": RELAY_DUPLEX_TIMING_KEYS[9:10],
    "CD": RELAY_DUPLEX_TIMING_KEYS[10:11],
    "REQUEST_SIDE": RELAY_DUPLEX_TIMING_KEYS[0:4]
    + RELAY_DUPLEX_TIMING_KEYS[8:9],
    "RESPONSE_SIDE": RELAY_DUPLEX_TIMING_KEYS[4:8]
    + RELAY_DUPLEX_TIMING_KEYS[10:11],
    "ALL": RELAY_DUPLEX_TIMING_KEYS,
}

BOUNDARY_SLOT_KEYS = {
    "A": "slot_indexed_session_relative_client_to_relay_receive_ns",
    "B": "slot_indexed_session_relative_relay_to_gateway_send_ns",
    "C": "slot_indexed_session_relative_gateway_to_relay_receive_ns",
    "D": "slot_indexed_session_relative_relay_to_client_send_ns",
}


def _segments(
    projection: Mapping[str, Any], raw_widths: Sequence[int]
) -> tuple[dict[str, list[float]], list[float]]:
    widths = tuple(int(value) for value in raw_widths)
    if len(widths) != len(RELAY_DUPLEX_TIMING_KEYS):
        raise ValueError("duplex attribution requires all eleven frozen raw widths")
    full = timing_feature_vector(projection, raw_widths=widths)
    segments: dict[str, list[float]] = {}
    offset = 0
    for key, width in zip(RELAY_DUPLEX_TIMING_KEYS, widths, strict=True):
        end = offset + width + 12
        segments[key] = full[offset:end]
        offset = end
    if offset + 1 != len(full):
        raise AssertionError("frozen Relay feature layout changed")
    return segments, full


def attribution_feature_vectors(
    projection: Mapping[str, Any], *, raw_widths: Sequence[int]
) -> dict[str, list[float]]:
    """Partition the frozen Relay vector without creating new information."""

    segments, full = _segments(projection, raw_widths)
    output: dict[str, list[float]] = {}
    for family in FEATURE_FAMILY_ORDER:
        if family == "ALL":
            output[family] = list(full)
            continue
        vector: list[float] = []
        for key in FEATURE_FAMILY_KEYS[family]:
            vector.extend(segments[key])
        output[family] = vector
    return output


def feature_family_contract(raw_widths: Sequence[int]) -> dict[str, Any]:
    widths = tuple(int(value) for value in raw_widths)
    if len(widths) != len(RELAY_DUPLEX_TIMING_KEYS):
        raise ValueError("wrong frozen duplex raw-width count")
    segment_width = {
        key: width + 12
        for key, width in zip(RELAY_DUPLEX_TIMING_KEYS, widths, strict=True)
    }
    return {
        family: {
            "projection_keys": list(FEATURE_FAMILY_KEYS[family]),
            "feature_width": (
                sum(segment_width[key] for key in FEATURE_FAMILY_KEYS[family])
                + (1 if family == "ALL" else 0)
            ),
            "global_total_session_span_included": family == "ALL",
        }
        for family in FEATURE_FAMILY_ORDER
    }
