from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

from v12_timing.sentinel_resume import (
    FAILURE_EXACT_ALPHA,
    IMMUTABLE_FAILED_IDENTITY,
    PLANNED_BLOCKS,
    PLANNED_EVAL_BLOCKS,
    PLANNED_TRAIN_BLOCKS,
    TOTAL_SESSIONS,
    build_freeze_manifest,
    completion_channel,
    exact_paired_binomial_two_sided,
    select_complete_blocks,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def old_identities() -> set[str]:
    payload = json.loads((ROOT / "V12_P10_TIMING_SENTINEL_FREEZE.json").read_text(encoding="utf-8"))
    return set(payload["identity_manifest"])


@pytest.fixture(scope="module")
def manifest(old_identities: set[str]) -> dict[str, object]:
    return build_freeze_manifest(
        execution_source_commit="test-source",
        analysis_hashes={},
        excluded_identities=sorted(old_identities),
        exclusion_sources={"old-freeze": "test-hash"},
    )


def _statuses(manifest: dict[str, object]) -> dict[str, str]:
    return {identity: "COMPLETE" for identity in manifest["identity_manifest"]}


def _identity_for(
    manifest: dict[str, object], coordinate_id: str, planned_block: int, label: int
) -> str:
    identities = manifest["identity_manifest"]
    return next(
        identity
        for identity, row in identities.items()
        if row["coordinate_id"] == coordinate_id
        and row["planned_block"] == planned_block
        and row["label"] == label
    )


def test_freeze_has_exact_5040_fresh_identities(
    manifest: dict[str, object], old_identities: set[str]
) -> None:
    validate_freeze_manifest(manifest, excluded_identities=old_identities)
    assert len(manifest["identity_manifest"]) == TOTAL_SESSIONS == 5040
    assert len(manifest["execution_schedule"]) == TOTAL_SESSIONS
    assert len(manifest["pairs"]) == 8 * PLANNED_BLOCKS == 2520
    assert set(manifest["identity_manifest"]).isdisjoint(old_identities)
    assert IMMUTABLE_FAILED_IDENTITY not in manifest["identity_manifest"]
    assert manifest["seed_search"] is False
    assert manifest["identity_search"] is False
    assert manifest["retry_policy"] == "ZERO_RETRY_ZERO_REPLACEMENT"


def test_partition_and_priority_are_exact_and_frozen(manifest: dict[str, object]) -> None:
    identities = manifest["identity_manifest"]
    for coordinate in manifest["physical_coordinates"]:
        coordinate_id = coordinate["coordinate_id"]
        rows = [row for row in identities.values() if row["coordinate_id"] == coordinate_id]
        train = {
            row["planned_block"]
            for row in rows
            if row["partition"] == "SENTINEL_TRAIN"
        }
        evaluation = {
            row["planned_block"]
            for row in rows
            if row["partition"] == "SENTINEL_EVAL"
        }
        assert len(rows) == 2 * PLANNED_BLOCKS
        assert len(train) == PLANNED_TRAIN_BLOCKS == 189
        assert len(evaluation) == PLANNED_EVAL_BLOCKS == 126
        assert train.isdisjoint(evaluation)
        for partition, expected_count in (
            ("SENTINEL_TRAIN", PLANNED_TRAIN_BLOCKS),
            ("SENTINEL_EVAL", PLANNED_EVAL_BLOCKS),
        ):
            priorities = {
                row["selection_priority"]
                for row in rows
                if row["partition"] == partition
            }
            assert priorities == set(range(expected_count))


def test_outer_schedule_interleaves_coordinates_and_classes(manifest: dict[str, object]) -> None:
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    for planned_block in range(PLANNED_BLOCKS):
        wave = schedule[planned_block * 16 : (planned_block + 1) * 16]
        assert len({row["coordinate_id"] for row in wave}) == 8
        for offset in range(0, 16, 2):
            pair = wave[offset : offset + 2]
            assert pair[0]["pair_id"] == pair[1]["pair_id"]
            assert sorted(identities[row["identity"]]["label"] for row in pair) == [0, 1]
    labels = [identities[row["identity"]]["label"] for row in schedule]
    longest = current = 1
    for before, after in pairwise(labels):
        current = current + 1 if before == after else 1
        longest = max(longest, current)
    assert longest <= 2


def test_complete_block_selection_uses_priority_and_never_partial_block(
    manifest: dict[str, object],
) -> None:
    statuses = _statuses(manifest)
    coordinate = manifest["physical_coordinates"][0]
    coordinate_id = coordinate["coordinate_id"]
    pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
    highest_train = min(
        (row for row in pairs if row["partition"] == "SENTINEL_TRAIN"),
        key=lambda row: row["selection_priority"],
    )
    failed_identity = highest_train["member_identities_in_execution_order"][0]
    statuses[failed_identity] = "FAILED"
    selection = select_complete_blocks(manifest, statuses)[coordinate_id]
    selected_train = set(selection["SENTINEL_TRAIN"]["selected_identities"])
    assert selection["SENTINEL_TRAIN"]["available_complete_blocks"] == 188
    assert len(selection["SENTINEL_TRAIN"]["selected_planned_blocks"]) == 180
    assert len(selected_train) == 360
    assert failed_identity not in selected_train
    assert highest_train["planned_block"] not in selection["SENTINEL_TRAIN"][
        "selected_planned_blocks"
    ]
    assert len(selection["SENTINEL_EVAL"]["selected_planned_blocks"]) == 120


def test_insufficient_complete_blocks_fails_closed(manifest: dict[str, object]) -> None:
    statuses = _statuses(manifest)
    coordinate_id = manifest["physical_coordinates"][0]["coordinate_id"]
    train_pairs = [
        row
        for row in manifest["pairs"]
        if row["coordinate_id"] == coordinate_id and row["partition"] == "SENTINEL_TRAIN"
    ]
    for pair in train_pairs[:10]:
        statuses[pair["member_identities_in_execution_order"][0]] = "FAILED"
    selection = select_complete_blocks(manifest, statuses)[coordinate_id]
    assert selection["SENTINEL_TRAIN"]["available_complete_blocks"] == 179
    assert selection["SENTINEL_TRAIN"]["sufficient"] is False


def test_exact_paired_diagnostic_and_failure_flags(manifest: dict[str, object]) -> None:
    assert exact_paired_binomial_two_sided(0, 0) == 1.0
    assert exact_paired_binomial_two_sided(1, 0) == 1.0
    assert exact_paired_binomial_two_sided(10, 0) == pytest.approx(2 / 1024)
    assert 2 / 1024 < FAILURE_EXACT_ALPHA

    coordinate_id = manifest["physical_coordinates"][0]["coordinate_id"]
    pairs = [row for row in manifest["pairs"] if row["coordinate_id"] == coordinate_id]
    statuses = _statuses(manifest)
    identities = manifest["identity_manifest"]
    for pair in pairs[:10]:
        by_label = {
            identities[identity]["label"]: identity
            for identity in pair["member_identities_in_execution_order"]
        }
        statuses[by_label[0]] = "FAILED"
    row = next(
        value
        for value in completion_channel(manifest, statuses)
        if value["coordinate_id"] == coordinate_id
    )
    assert row["class0_failures"] == 10
    assert row["class1_failures"] == 0
    assert row["failure_channel_flag"] is True
    assert row["operational_reliability_concern"] is True


def test_one_isolated_failure_is_reported_but_does_not_flag(manifest: dict[str, object]) -> None:
    statuses = _statuses(manifest)
    coordinate_id = manifest["physical_coordinates"][0]["coordinate_id"]
    statuses[_identity_for(manifest, coordinate_id, 0, 1)] = "FAILED"
    row = next(
        value
        for value in completion_channel(manifest, statuses)
        if value["coordinate_id"] == coordinate_id
    )
    assert row["class1_failures"] == 1
    assert row["asymmetric_incomplete_blocks"] == 1
    assert row["paired_exact_two_sided_p"] == 1.0
    assert row["failure_channel_flag"] is False
    assert row["operational_reliability_concern"] is False


def test_feature_contract_excludes_failure_and_private_metadata(
    manifest: dict[str, object],
) -> None:
    contract = manifest["feature_contract"]
    assert contract["view"] == "TIMING_ONLY_VIEW"
    assert contract["failure_status_feature"] is False
    assert contract["absolute_wall_clock_feature"] is False
    assert contract["experiment_ordinal_feature"] is False
    assert contract["block_id_feature"] is False


def test_manifest_payload_tampering_fails_closed(manifest: dict[str, object]) -> None:
    tampered = dict(manifest)
    tampered["total_physical_sessions"] = 5039
    with pytest.raises(ValueError, match="payload hash drifted"):
        validate_freeze_manifest(tampered)


def test_collector_has_no_classifier_training_or_auc_path() -> None:
    source = (ROOT / "scripts" / "collect_v12_p10_timing_sentinel_resume.py").read_text(
        encoding="utf-8"
    )
    assert "sklearn" not in source
    assert "roc_auc" not in source
    assert "select_on_train" not in source
    assert "matched_block_bootstrap" not in source
