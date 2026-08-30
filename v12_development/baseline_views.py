from __future__ import annotations

from typing import Any


BASELINES = (
    "B0_DIRECT_NATIVE",
    "B1_PIR_PLUS_DIRECT_ACTION",
    "B2_PIR_PLUS_OHTTP_UNSHAPED",
    "B3_PIR_PLUS_OHTTP_PADDED",
    "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL",
    "B5_FULL_STRICT",
)

DIMENSIONS = (
    "P1_AGENT_IDENTITY", "P2_TOOL_ROUTE_IDENTITY", "P3_ACTION_KIND",
    "P4_ACTUAL_ACTION_COUNT", "P5_REPETITION", "P6_FREQUENCY_SKEW",
    "P7_RARE_TARGET", "P8_TRANSITION_ORDER", "P9_PRIVATE_ARGUMENT_SIZE",
    "P10_PROVIDER_READINESS", "P11_INTERNAL_EXTERNAL", "P12_CAUSAL_DEPTH",
    "P13_AGENT_SERVICE_SUBTYPE", "P14_DYNAMIC_PRIVATE_RESOLUTION",
)


def _private_workload(dimension: str, arm: str) -> dict[str, Any]:
    changed = arm == "B"
    return {
        "agent": "agent.b" if changed and dimension == "P1_AGENT_IDENTITY" else "agent.a",
        "route": "tool.b" if changed and dimension == "P2_TOOL_ROUTE_IDENTITY" else "tool.a",
        "kind": "AGENT_SERVICE" if changed and dimension == "P3_ACTION_KIND" else "TOOL",
        "count": 7 if changed and dimension == "P4_ACTUAL_ACTION_COUNT" else 3,
        "pattern": ("ABAB" if changed else "AAAA") if dimension in {"P5_REPETITION", "P6_FREQUENCY_SKEW", "P7_RARE_TARGET", "P8_TRANSITION_ORDER"} else "AAAA",
        "argument_bytes": 700 if changed and dimension == "P9_PRIVATE_ARGUMENT_SIZE" else 20,
        "readiness": "LATE" if changed and dimension == "P10_PROVIDER_READINESS" else "EARLY",
        "placement": "INTERNAL" if changed and dimension == "P11_INTERNAL_EXTERNAL" else "EXTERNAL",
        "depth": 3 if changed and dimension == "P12_CAUSAL_DEPTH" else 1,
        "subtype": "HANDOFF" if changed and dimension == "P13_AGENT_SERVICE_SUBTYPE" else "AGENT_AS_TOOL",
        "resolution_delay": 30 if changed and dimension == "P14_DYNAMIC_PRIVATE_RESOLUTION" else 0,
    }


def public_view(baseline: str, dimension: str, arm: str) -> dict[str, Any]:
    private = _private_workload(dimension, arm)
    count = int(private["count"])
    if baseline in {"B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL", "B5_FULL_STRICT"}:
        count = 356
    if baseline == "B0_DIRECT_NATIVE":
        return {**private, "endpoint": private["route"], "requests": count, "responses": count, "request_sizes": [private["argument_bytes"]] * count, "lifetime": count}
    if baseline == "B1_PIR_PLUS_DIRECT_ACTION":
        return {key: value for key, value in public_view("B0_DIRECT_NATIVE", dimension, arm).items() if key != "agent"}
    if baseline == "B2_PIR_PLUS_OHTTP_UNSHAPED":
        return {"endpoint": "OHTTP_RELAY", "requests": count, "responses": count, "request_sizes": [55 + private["argument_bytes"]] * count, "response_sizes": [64] * count, "lifetime": count}
    if baseline == "B3_PIR_PLUS_OHTTP_PADDED":
        return {"endpoint": "OHTTP_RELAY", "requests": count, "responses": count, "request_sizes": [1079] * count, "response_sizes": [800] * count, "lifetime": count}
    if baseline == "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL":
        return {"endpoint": "INTERNAL_DIRECT" if private["placement"] == "INTERNAL" else "OHTTP_RELAY", "requests": count, "responses": count, "request_sizes": [1079] * count, "response_sizes": [800] * count, "lifetime": 3560}
    if baseline == "B5_FULL_STRICT":
        return {"endpoint": "STRICT_COMMON_RELAY", "requests": 356, "responses": 356, "request_sizes": [1079] * 356, "response_sizes": [800] * 356, "lifetime": 3560}
    raise ValueError(baseline)


def comparison(baseline: str, dimension: str) -> dict[str, Any]:
    a, b = public_view(baseline, dimension, "A"), public_view(baseline, dimension, "B")
    return {
        "baseline": baseline, "dimension": dimension,
        "full_public_structural_projection_equal": a == b,
        "size_projection_equal": a.get("request_sizes") == b.get("request_sizes") and a.get("response_sizes") == b.get("response_sizes"),
        "request_count_equal": a["requests"] == b["requests"],
        "response_count_equal": a["responses"] == b["responses"],
        "scheduled_lifetime_equal": a["lifetime"] == b["lifetime"],
        "endpoint_connection_view_equal": a["endpoint"] == b["endpoint"],
    }
