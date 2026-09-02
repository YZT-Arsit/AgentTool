from __future__ import annotations

import pytest

from v12_timing.attribution import (
    dominant_timing_source,
    expected_family_widths,
    feature_family_vector,
    observer_feature_families,
)
from v12_timing.projection import timing_feature_vector


def _relay_projection() -> dict[str, object]:
    return {
        "observer": "RELAY",
        "view": "TIMING_ONLY_VIEW",
        "slot_indexed_session_relative_request_ns": [0, 3, 7],
        "chronological_request_inter_arrival_ns": [3, 4],
        "slot_indexed_session_relative_response_send_ns": [2, 6, 11],
        "chronological_response_send_inter_arrival_ns": [4, 5],
        "slot_paired_request_response_ns": [2, 3, 4],
        "total_session_span_ns": 11,
    }


def _registry_projection() -> dict[str, object]:
    return {
        "observer": "REGISTRY",
        "view": "TIMING_ONLY_VIEW",
        "session_relative_query_arrival_ns": [0, 5, 10],
        "inter_query_gap_ns": [5, 5],
        "session_relative_response_send_ns": [2, 8, 14],
        "query_response_ns": [2, 3, 4],
        "total_resolution_session_span_ns": 14,
    }


def test_relay_families_are_exact_slices_of_frozen_v3_vector() -> None:
    projection = _relay_projection()
    widths = (3, 2, 3, 2, 3)
    families = observer_feature_families("RELAY")
    expected = expected_family_widths("RELAY", widths)
    assert families == (
        "RELAY_REQUEST_ONLY",
        "RELAY_RESPONSE_ONLY",
        "RELAY_SLOT_LATENCY_ONLY",
        "RELAY_REQUEST_PLUS_RESPONSE",
        "RELAY_ALL",
    )
    for family in families:
        assert (
            len(feature_family_vector(projection, raw_widths=widths, family=family))
            == expected[family]
        )
    assert feature_family_vector(
        projection, raw_widths=widths, family="RELAY_ALL"
    ) == timing_feature_vector(projection, raw_widths=widths)


def test_registry_families_are_exact_slices_of_frozen_v3_vector() -> None:
    projection = _registry_projection()
    widths = (3, 2, 3, 3)
    families = observer_feature_families("REGISTRY")
    expected = expected_family_widths("REGISTRY", widths)
    for family in families:
        assert (
            len(feature_family_vector(projection, raw_widths=widths, family=family))
            == expected[family]
        )
    assert feature_family_vector(
        projection, raw_widths=widths, family="REGISTRY_ALL"
    ) == timing_feature_vector(projection, raw_widths=widths)


def test_subset_families_exclude_total_span_and_unselected_sequences() -> None:
    relay = _relay_projection()
    request = feature_family_vector(
        relay, raw_widths=(3, 2, 3, 2, 3), family="RELAY_REQUEST_ONLY"
    )
    assert len(request) == 3 + 12 + 2 + 12
    assert request[-1] != relay["total_session_span_ns"]


def test_unknown_observer_fails_closed() -> None:
    projection = {**_relay_projection(), "observer": "UNKNOWN"}
    with pytest.raises(ValueError, match="unknown timing observer"):
        feature_family_vector(
            projection, raw_widths=(3, 2, 3, 2, 3), family="RELAY_ALL"
        )
    with pytest.raises(ValueError, match="unknown timing observer"):
        expected_family_widths("UNKNOWN", (3,))


def test_descriptive_source_classification_reuses_frozen_boundary() -> None:
    base = {
        "RELAY_REQUEST_ONLY": 0.50,
        "RELAY_RESPONSE_ONLY": 0.50,
        "RELAY_SLOT_LATENCY_ONLY": 0.50,
        "RELAY_REQUEST_PLUS_RESPONSE": 0.50,
        "RELAY_ALL": 0.60,
    }
    assert dominant_timing_source("RELAY", base) == "CORRELATION_ONLY"
    assert (
        dominant_timing_source("RELAY", {**base, "RELAY_REQUEST_ONLY": 0.60})
        == "REQUEST_SIDE"
    )
    assert (
        dominant_timing_source("RELAY", {**base, "RELAY_RESPONSE_ONLY": 0.60})
        == "RESPONSE_SIDE"
    )
    assert (
        dominant_timing_source("RELAY", {**base, "RELAY_SLOT_LATENCY_ONLY": 0.60})
        == "SLOT_LATENCY"
    )
    assert (
        dominant_timing_source(
            "RELAY",
            {**base, "RELAY_REQUEST_ONLY": 0.60, "RELAY_RESPONSE_ONLY": 0.60},
        )
        == "BOTH"
    )
