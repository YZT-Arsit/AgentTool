from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .projection import timing_feature_vector

RELAY_FAMILIES: dict[str, tuple[int, ...]] = {
    "RELAY_REQUEST_ONLY": (0, 1),
    "RELAY_RESPONSE_ONLY": (2, 3),
    "RELAY_SLOT_LATENCY_ONLY": (4,),
    "RELAY_REQUEST_PLUS_RESPONSE": (0, 1, 2, 3),
    "RELAY_ALL": (0, 1, 2, 3, 4),
}
REGISTRY_FAMILIES: dict[str, tuple[int, ...]] = {
    "REGISTRY_REQUEST_ONLY": (0, 1),
    "REGISTRY_RESPONSE_ONLY": (2,),
    "REGISTRY_QUERY_RESPONSE_ONLY": (3,),
    "REGISTRY_REQUEST_PLUS_RESPONSE": (0, 1, 2),
    "REGISTRY_ALL": (0, 1, 2, 3),
}


def observer_feature_families(observer: str) -> tuple[str, ...]:
    if observer == "RELAY":
        return tuple(RELAY_FAMILIES)
    if observer == "REGISTRY":
        return tuple(REGISTRY_FAMILIES)
    raise ValueError("unknown timing observer")


def feature_family_vector(
    projection: Mapping[str, Any],
    *,
    raw_widths: Sequence[int],
    family: str,
) -> list[float]:
    """Select frozen V3 sequence segments without adding new information."""

    observer = str(projection.get("observer"))
    if observer == "RELAY":
        families = RELAY_FAMILIES
    elif observer == "REGISTRY":
        families = REGISTRY_FAMILIES
    else:
        raise ValueError("unknown timing observer")
    if family not in families:
        raise ValueError(f"feature family {family!r} is invalid for {observer!r}")
    widths = tuple(int(value) for value in raw_widths)
    if len(widths) != len(families[next(reversed(families))]):
        raise ValueError("raw timing widths do not match the observer family schema")
    full = timing_feature_vector(projection, raw_widths=widths)
    segments: list[list[float]] = []
    offset = 0
    for width in widths:
        end = offset + width + 12
        segments.append(full[offset:end])
        offset = end
    if offset + 1 != len(full):
        raise AssertionError("frozen V3 feature layout changed")
    selected = [value for index in families[family] for value in segments[index]]
    if family.endswith("_ALL"):
        selected.append(full[-1])
    return selected


def expected_family_widths(observer: str, raw_widths: Sequence[int]) -> dict[str, int]:
    if observer == "RELAY":
        families = RELAY_FAMILIES
    elif observer == "REGISTRY":
        families = REGISTRY_FAMILIES
    else:
        raise ValueError("unknown timing observer")
    widths = tuple(int(value) + 12 for value in raw_widths)
    return {
        family: sum(widths[index] for index in indices)
        + (1 if family.endswith("_ALL") else 0)
        for family, indices in families.items()
    }


def dominant_timing_source(observer: str, family_lcb99_5: Mapping[str, float]) -> str:
    """Descriptive attribution using the already frozen 0.55 sentinel boundary."""

    prefix = "RELAY" if observer == "RELAY" else "REGISTRY"
    request = family_lcb99_5[f"{prefix}_REQUEST_ONLY"] > 0.55
    response = family_lcb99_5[f"{prefix}_RESPONSE_ONLY"] > 0.55
    latency_name = (
        "RELAY_SLOT_LATENCY_ONLY"
        if observer == "RELAY"
        else "REGISTRY_QUERY_RESPONSE_ONLY"
    )
    latency = family_lcb99_5[latency_name] > 0.55
    combined = family_lcb99_5[f"{prefix}_REQUEST_PLUS_RESPONSE"] > 0.55
    all_signal = family_lcb99_5[f"{prefix}_ALL"] > 0.55
    if request and (response or latency):
        return "BOTH"
    if request:
        return "REQUEST_SIDE"
    if response:
        return "RESPONSE_SIDE"
    if latency:
        return "SLOT_LATENCY"
    if combined or all_signal:
        return "CORRELATION_ONLY"
    return "MIXED"
