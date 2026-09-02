from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from v12_timing.classifier import sklearn_random_state
from v12_timing.sentinel_smoke import (
    SMOKE_FAILURE_MARGIN,
    SMOKE_LCB_QUANTILE,
    TOTAL_SESSIONS,
    build_freeze_manifest,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def freeze() -> dict[str, object]:
    return build_freeze_manifest(
        execution_source_commit="a" * 40,
        analysis_hashes={"fixture": hashlib.sha256(b"fixture").hexdigest()},
        excluded_identities=["DEV-TAD-P10-T7-OA-SENTINEL-B20000-C0"],
        exclusion_sources={"prior": hashlib.sha256(b"prior").hexdigest()},
    )


def test_smoke_denominator_coordinate_and_observer_contract(
    freeze: dict[str, object],
) -> None:
    assert freeze["physical_coordinate_count"] == 5
    assert freeze["observer_comparison_count"] == 7
    assert freeze["planned_train_blocks_per_coordinate"] == 32
    assert freeze["planned_eval_blocks_per_coordinate"] == 32
    assert freeze["target_train_complete_blocks"] == 30
    assert freeze["target_eval_complete_blocks"] == 30
    assert len(freeze["identity_manifest"]) == TOTAL_SESSIONS == 640
    assert len(freeze["pairs"]) == 320


def test_smoke_identities_are_fresh_paired_and_one_use(
    freeze: dict[str, object],
) -> None:
    identities = freeze["identity_manifest"]
    schedule = freeze["execution_schedule"]
    assert len(schedule) == len({row["identity"] for row in schedule}) == 640
    assert all("B300" in identity for identity in identities)
    for pair in freeze["pairs"]:
        rows = [
            identities[value] for value in pair["member_identities_in_execution_order"]
        ]
        assert sorted(row["label"] for row in rows) == [0, 1]
        assert (
            rows[0]["public_profile_signature"] == rows[1]["public_profile_signature"]
        )
    validate_freeze_manifest(
        freeze, excluded_identities=["DEV-TAD-P10-T7-OA-SENTINEL-B20000-C0"]
    )


def test_smoke_feature_and_decision_rule_are_fixed(freeze: dict[str, object]) -> None:
    assert freeze["feature_contract"]["RELAY_feature_width"] == 5695
    assert freeze["feature_contract"]["REGISTRY_feature_width"] == 448
    assert not freeze["feature_contract"]["failure_status_feature"]
    assert not freeze["feature_contract"]["private_semantic_feature"]
    assert SMOKE_LCB_QUANTILE == 0.05
    assert SMOKE_FAILURE_MARGIN == 0.65
    protocol = json.loads(
        (ROOT / "V12_DUPLEX_REPAIR_SMOKE_SENTINEL_PROTOCOL_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )
    assert protocol["planned_sessions"] == 640
    assert (
        protocol["statistics"]["smoke_failure_rule"]
        == "ANY comparison one-sided LCB95 > 0.65"
    )


def test_smoke_raw_and_estimator_seeds_are_predeclared(
    freeze: dict[str, object],
) -> None:
    normalized = []
    for coordinate in freeze["physical_coordinates"]:
        for observer_index, _observer in enumerate(coordinate["observers"]):
            raw = coordinate["analysis_seed"] + observer_index
            normalized.append(sklearn_random_state(raw))
            assert 0 <= normalized[-1] <= 2**32 - 1
    assert len(normalized) == len(set(normalized)) == 7
