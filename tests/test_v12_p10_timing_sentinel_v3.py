from __future__ import annotations

import importlib.util
import json
from itertools import pairwise
from pathlib import Path

import pytest

from v12_timing.sentinel_v3 import (
    FAILURE_EXACT_ALPHA,
    METHODOLOGY_BASE_SHA,
    PLANNED_BLOCKS,
    PLANNED_EVAL_BLOCKS,
    PLANNED_TRAIN_BLOCKS,
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    WORKLOAD_BLOCK_OFFSET,
    build_freeze_manifest,
    completion_channel,
    exact_paired_binomial_two_sided,
    select_complete_blocks,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_freeze_module():
    path = ROOT / "scripts/freeze_v12_p10_timing_sentinel_v3.py"
    spec = importlib.util.spec_from_file_location("freeze_v3_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prior_identities() -> set[str]:
    module = _load_freeze_module()
    identities, _ = module._exclusions()
    return set(identities)


@pytest.fixture(scope="module")
def manifest(prior_identities: set[str]) -> dict[str, object]:
    return build_freeze_manifest(
        execution_source_commit="test-source",
        analysis_hashes={},
        excluded_identities=sorted(prior_identities),
        exclusion_sources={"test": "hash"},
    )


def _statuses(manifest: dict[str, object]) -> dict[str, str]:
    return {identity: "COMPLETE" for identity in manifest["identity_manifest"]}


def test_freeze_has_fresh_exact_denominator_and_v3_feature_contract(
    manifest: dict[str, object], prior_identities: set[str]
) -> None:
    validate_freeze_manifest(manifest, excluded_identities=prior_identities)
    assert manifest["methodology_base_sha"] == METHODOLOGY_BASE_SHA
    assert len(manifest["identity_manifest"]) == TOTAL_SESSIONS == 5040
    assert len(manifest["pairs"]) == 8 * PLANNED_BLOCKS == 2520
    assert set(manifest["identity_manifest"]).isdisjoint(prior_identities)
    assert manifest["workload_block_offset"] == WORKLOAD_BLOCK_OFFSET == 6000
    assert manifest["feature_contract"]["RELAY_raw_widths"] == [506, 505, 506, 505, 506]
    assert manifest["feature_contract"]["RELAY_feature_width"] == 2589


def test_all_prior_resume_and_original_identities_are_excluded(
    prior_identities: set[str],
) -> None:
    for relative in (
        "V12_P10_TIMING_SENTINEL_FREEZE.json",
        "V12_P10_TIMING_SENTINEL_RESUME_FREEZE.json",
    ):
        payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert set(payload["identity_manifest"]).issubset(prior_identities)


def test_partition_priority_and_outer_schedule_are_frozen(
    manifest: dict[str, object],
) -> None:
    identities = manifest["identity_manifest"]
    for coordinate in manifest["physical_coordinates"]:
        rows = [
            row for row in identities.values()
            if row["coordinate_id"] == coordinate["coordinate_id"]
        ]
        train = {row["planned_block"] for row in rows if row["partition"] == "SENTINEL_TRAIN"}
        evaluation = {
            row["planned_block"] for row in rows if row["partition"] == "SENTINEL_EVAL"
        }
        assert len(train) == PLANNED_TRAIN_BLOCKS == 189
        assert len(evaluation) == PLANNED_EVAL_BLOCKS == 126
        assert train.isdisjoint(evaluation)
    labels = [
        identities[row["identity"]]["label"] for row in manifest["execution_schedule"]
    ]
    longest = current = 1
    for before, after in pairwise(labels):
        current = current + 1 if before == after else 1
        longest = max(longest, current)
    assert longest <= 2


def test_complete_block_selection_uses_only_frozen_priority(
    manifest: dict[str, object],
) -> None:
    statuses = _statuses(manifest)
    coordinate_id = manifest["physical_coordinates"][0]["coordinate_id"]
    pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
    first_train = min(
        (row for row in pairs if row["partition"] == "SENTINEL_TRAIN"),
        key=lambda row: row["selection_priority"],
    )
    statuses[first_train["member_identities_in_execution_order"][0]] = "FAILED"
    selected = select_complete_blocks(manifest, statuses)[coordinate_id]
    assert selected["SENTINEL_TRAIN"]["available_complete_blocks"] == 188
    assert len(selected["SENTINEL_TRAIN"]["selected_planned_blocks"]) == (
        TARGET_TRAIN_COMPLETE_BLOCKS
    )
    assert len(selected["SENTINEL_EVAL"]["selected_planned_blocks"]) == (
        TARGET_EVAL_COMPLETE_BLOCKS
    )
    assert first_train["planned_block"] not in selected["SENTINEL_TRAIN"][
        "selected_planned_blocks"
    ]


def test_failure_channel_exact_rule_is_preserved(manifest: dict[str, object]) -> None:
    assert exact_paired_binomial_two_sided(10, 0) == pytest.approx(2 / 1024)
    assert 2 / 1024 < FAILURE_EXACT_ALPHA
    statuses = _statuses(manifest)
    coordinate_id = manifest["physical_coordinates"][0]["coordinate_id"]
    identities = manifest["identity_manifest"]
    pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
    for pair in pairs[:10]:
        by_label = {
            identities[identity]["label"]: identity
            for identity in pair["member_identities_in_execution_order"]
        }
        statuses[by_label[0]] = "FAILED"
    row = next(
        row for row in completion_channel(manifest, statuses)
        if row["coordinate_id"] == coordinate_id
    )
    assert row["failure_channel_flag"] is True
    assert row["operational_reliability_concern"] is True


def test_collection_source_contains_no_classifier_or_auc_path() -> None:
    sources = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "scripts/collect_v12_p10_timing_sentinel_resume.py",
            "scripts/collect_v12_p10_timing_sentinel_v3.py",
        )
    )
    assert "sklearn" not in sources
    assert "roc_auc" not in sources
    assert "select_on_train" not in sources
    assert "matched_block_bootstrap" not in sources
    assert "chronological_request_inter_arrival_ns" in sources
    assert "complete_unique_relay_slot_set" in sources


def test_manifest_tampering_fails_closed(manifest: dict[str, object]) -> None:
    tampered = dict(manifest)
    tampered["total_physical_sessions"] = 5039
    with pytest.raises(ValueError, match="payload hash drifted"):
        validate_freeze_manifest(tampered)
