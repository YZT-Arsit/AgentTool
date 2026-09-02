from __future__ import annotations

from pathlib import Path

from scripts.analyze_v12_v4r7_residual_timing_attribution import (
    _load_archive_records,
)
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    RELAY_DUPLEX_TIMING_KEYS,
    timing_feature_vector,
)
from v12_timing.residual_attribution import (
    FEATURE_FAMILY_KEYS,
    FEATURE_FAMILY_ORDER,
    attribution_feature_vectors,
    feature_family_contract,
)


def projection_fixture(rounds: int = 5) -> dict[str, object]:
    base = [index * 100 for index in range(rounds)]
    projection: dict[str, object] = {
        "observer": "RELAY",
        "view": DUPLEX_TIMING_ONLY_VIEW,
        "profile_id": "fixture",
        "public_session_ids": ["fixture"] * rounds,
        "public_slot_order": list(range(1, rounds + 1)),
        "authenticated_slot_order": list(range(1, rounds + 1)),
        "request_bytes": [1079] * rounds,
        "response_bytes": [800] * rounds,
        "total_session_span_ns": 450,
    }
    boundary_offsets = (0, 10, 40, 50)
    for offset, keys in zip(boundary_offsets, range(0, 8, 2), strict=True):
        values = [value + offset for value in base]
        projection[RELAY_DUPLEX_TIMING_KEYS[keys]] = values
        projection[RELAY_DUPLEX_TIMING_KEYS[keys + 1]] = [100] * (rounds - 1)
    projection[RELAY_DUPLEX_TIMING_KEYS[8]] = [10] * rounds
    projection[RELAY_DUPLEX_TIMING_KEYS[9]] = [30] * rounds
    projection[RELAY_DUPLEX_TIMING_KEYS[10]] = [10] * rounds
    return projection


def test_attribution_families_are_exact_frozen_vector_slices() -> None:
    projection = projection_fixture()
    widths = (5, 4, 5, 4, 5, 4, 5, 4, 5, 5, 5)
    vectors = attribution_feature_vectors(projection, raw_widths=widths)
    contract = feature_family_contract(widths)
    assert tuple(vectors) == FEATURE_FAMILY_ORDER
    assert vectors["ALL"] == timing_feature_vector(projection, raw_widths=widths)
    assert {name: len(vector) for name, vector in vectors.items()} == {
        name: row["feature_width"] for name, row in contract.items()
    }
    assert len(vectors["A"]) == len(vectors["B"]) == 33
    assert len(vectors["AB"]) == 17
    assert len(vectors["REQUEST_SIDE"]) == 83
    assert len(vectors["ALL"]) == 184


def test_subsets_do_not_mix_boundaries_or_add_global_span() -> None:
    contract = feature_family_contract((5, 4, 5, 4, 5, 4, 5, 4, 5, 5, 5))
    assert contract["REQUEST_SIDE"]["projection_keys"] == list(
        FEATURE_FAMILY_KEYS["A"]
        + FEATURE_FAMILY_KEYS["B"]
        + FEATURE_FAMILY_KEYS["AB"]
    )
    assert contract["RESPONSE_SIDE"]["projection_keys"] == list(
        FEATURE_FAMILY_KEYS["C"]
        + FEATURE_FAMILY_KEYS["D"]
        + FEATURE_FAMILY_KEYS["CD"]
    )
    assert all(
        not row["global_total_session_span_included"]
        for name, row in contract.items()
        if name != "ALL"
    )
    assert contract["ALL"]["global_total_session_span_included"] is True


def test_immutable_smoke_archive_is_complete_and_hash_valid() -> None:
    evidence = (
        Path(__file__).resolve().parents[1]
        / "V12_V4R7_SMOKE_COLLECTOR_LATE_FRAME_CLOSURE_EVIDENCE"
    )
    records, dataset = _load_archive_records(evidence)
    assert len(records) == 640
    assert len({row["identity"] for row in records}) == 640
    assert dataset["collection_closed"] is True
    assert dataset["common_integrity_abort"] is False
