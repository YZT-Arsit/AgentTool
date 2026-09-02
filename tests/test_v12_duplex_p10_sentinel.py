from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from v12_timing.classifier import sklearn_random_state
from v12_timing.sentinel_duplex import (
    BASE_DUPLEX_EVIDENCE,
    PLANNED_BLOCKS,
    TOTAL_SESSIONS,
    build_freeze_manifest,
    p10_profile,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def freeze() -> dict[str, object]:
    return build_freeze_manifest(
        execution_source_commit="f" * 40,
        analysis_hashes={"synthetic": hashlib.sha256(b"synthetic").hexdigest()},
        excluded_identities=["DEV-TAD-P10-T7-MS-SENTINEL-B0075-C1"],
        exclusion_sources={"synthetic": hashlib.sha256(b"excluded").hexdigest()},
    )


def test_p10_duplex_profile_and_denominators_are_exact(
    freeze: dict[str, object],
) -> None:
    profile = p10_profile()
    assert profile.admission_horizon_ms == 4500
    assert profile.round_period_ms == 10
    assert profile.total_rounds == 506
    assert profile.pir_resolution_opportunities == 100
    assert freeze["base_duplex_evidence"] == BASE_DUPLEX_EVIDENCE
    assert freeze["physical_coordinate_count"] == 8
    assert freeze["observer_comparison_count"] == 10
    assert len(freeze["pairs"]) == 8 * PLANNED_BLOCKS
    assert len(freeze["identity_manifest"]) == TOTAL_SESSIONS
    assert len(freeze["execution_schedule"]) == TOTAL_SESSIONS


def test_manifest_is_fresh_one_use_interleaved_and_block_matched(
    freeze: dict[str, object],
) -> None:
    identities = freeze["identity_manifest"]
    schedule = freeze["execution_schedule"]
    assert len({row["identity"] for row in schedule}) == TOTAL_SESSIONS
    assert all("B20" in identity for identity in identities)
    for pair in freeze["pairs"]:
        members = [
            identities[value] for value in pair["member_identities_in_execution_order"]
        ]
        assert sorted(row["label"] for row in members) == [0, 1]
        assert (
            members[0]["public_profile_signature"]
            == members[1]["public_profile_signature"]
        )
    first_block = [
        row["coordinate_id"] for row in schedule if row["planned_block"] == 0
    ]
    assert len(set(first_block)) == 8


def test_feature_contract_is_fixed_width_and_private_free(
    freeze: dict[str, object],
) -> None:
    contract = freeze["feature_contract"]
    assert contract["RELAY_raw_widths"] == [
        506,
        505,
        506,
        505,
        506,
        505,
        506,
        505,
        506,
        506,
        506,
    ]
    assert contract["RELAY_feature_width"] == 5695
    assert contract["REGISTRY_feature_width"] == 448
    assert not contract["absolute_wall_clock_feature"]
    assert not contract["experiment_ordinal_feature"]
    assert not contract["block_id_feature"]
    assert not contract["failure_status_feature"]
    assert not contract["private_semantic_feature"]
    validate_freeze_manifest(
        freeze, excluded_identities=["DEV-TAD-P10-T7-MS-SENTINEL-B0075-C1"]
    )


def test_seed_mapping_is_predeclared_uint32_without_changing_raw_fold_order(
    freeze: dict[str, object],
) -> None:
    seen = []
    for coordinate in freeze["physical_coordinates"]:
        raw = coordinate["analysis_seed"]
        assert raw >= 0
        assert 0 <= sklearn_random_state(raw) <= 2**32 - 1
        for model_index in range(4):
            for fold_index in range(5):
                raw_fold = raw + 10_000 * (model_index + 1) + fold_index
                seen.append(sklearn_random_state(raw_fold))
    assert len(seen) == len(set(seen))


def test_collection_wrapper_requires_complete_duplex_timing() -> None:
    source = (ROOT / "scripts" / "collect_v12_p10_timing_sentinel_resume.py").read_text(
        encoding="utf-8"
    )
    assert "require_duplex_application_timing=duplex_timing" in source
    assert "complete_duplex_relay_boundaries" in source
    assert "gateway_response_clock_complete" in source


def test_protocol_freeze_matches_manifest_contract(freeze: dict[str, object]) -> None:
    protocol = json.loads(
        (ROOT / "V12_DUPLEX_P10_SENTINEL_PROTOCOL_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )
    assert protocol["planned_identities"] == freeze["total_physical_sessions"] == 5040
    assert (
        protocol["feature_contract"]["Relay_feature_width"]
        == freeze["feature_contract"]["RELAY_feature_width"]
    )
    assert (
        protocol["feature_contract"]["Registry_feature_width"]
        == freeze["feature_contract"]["REGISTRY_feature_width"]
    )
