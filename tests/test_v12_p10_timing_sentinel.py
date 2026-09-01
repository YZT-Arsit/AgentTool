from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

from v12_timing.isolated_tasks import AUXILIARY_REGISTRY_COMPOSITE, task_isolation_audit
from v12_timing.sentinel import (
    build_freeze_manifest,
    build_sentinel_workload,
    physical_coordinates,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, object]:
    return build_freeze_manifest(execution_source_commit="test-commit", analysis_hashes={})


def test_sentinel_coordinate_and_observer_counts_are_exact() -> None:
    coordinates = physical_coordinates()
    assert len(coordinates) == 8
    assert sum(len(row.observers) for row in coordinates) == 10
    assert {
        (row.task_id, row.framework, row.observers) for row in coordinates
    } == {
        (task, framework, observers)
        for task, observers in (
            (AUXILIARY_REGISTRY_COMPOSITE, ("REGISTRY",)),
            ("T4", ("RELAY",)),
            ("T7", ("REGISTRY", "RELAY")),
            ("T9", ("RELAY",)),
        )
        for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework")
    }


def test_c1_is_explicitly_composite_and_uses_fixed_q_construction() -> None:
    left = build_sentinel_workload(
        AUXILIARY_REGISTRY_COMPOSITE, "OpenAI Agents SDK", 0, block=0
    )
    right = build_sentinel_workload(
        AUXILIARY_REGISTRY_COMPOSITE, "OpenAI Agents SDK", 1, block=0
    )
    assert left.task_id == right.task_id == AUXILIARY_REGISTRY_COMPOSITE
    assert left.claim_observers == right.claim_observers == ("REGISTRY",)
    assert len(left.cases) == len(right.cases) == 6
    assert {case.agent_id for case in left.cases} == {10}
    assert {case.agent_id for case in right.cases} == {10, 21}
    assert task_isolation_audit(AUXILIARY_REGISTRY_COMPOSITE, "OpenAI Agents SDK")["pass"]


def test_freeze_has_2400_complete_pairs_and_4800_unique_identities() -> None:
    manifest = _manifest()
    validate_freeze_manifest(manifest)
    assert len(manifest["pairs"]) == 2400
    assert len(manifest["identity_manifest"]) == 4800
    assert len(manifest["execution_schedule"]) == 4800
    assert manifest["seed_search"] is False
    assert manifest["identity_search"] is False
    assert manifest["retry_policy"] == "ZERO_RETRY_ZERO_REPLACEMENT"
    identities = manifest["identity_manifest"]
    for pair in manifest["pairs"]:
        members = pair["member_identities_in_execution_order"]
        assert sorted(identities[value]["label"] for value in members) == [0, 1]
        assert identities[members[0]]["public_profile_signature"] == identities[members[1]][
            "public_profile_signature"
        ]


def test_train_eval_partitions_are_exact_and_disjoint_per_coordinate() -> None:
    manifest = _manifest()
    identities = manifest["identity_manifest"]
    for coordinate in manifest["physical_coordinates"]:
        rows = [
            value
            for value in identities.values()
            if value["coordinate_id"] == coordinate["coordinate_id"]
        ]
        train = {value["block"] for value in rows if value["partition"] == "SENTINEL_TRAIN"}
        evaluation = {
            value["block"] for value in rows if value["partition"] == "SENTINEL_EVAL"
        }
        assert len(rows) == 600
        assert len(train) == 180
        assert len(evaluation) == 120
        assert train.isdisjoint(evaluation)


def test_outer_schedule_interleaves_coordinates_and_pair_members() -> None:
    manifest = _manifest()
    identities = manifest["identity_manifest"]
    schedule = manifest["execution_schedule"]
    for block in range(300):
        wave = schedule[block * 16 : (block + 1) * 16]
        assert len({row["coordinate_id"] for row in wave}) == 8
        for offset in range(0, 16, 2):
            pair = wave[offset : offset + 2]
            assert pair[0]["pair_id"] == pair[1]["pair_id"]
            assert sorted(identities[row["identity"]]["label"] for row in pair) == [0, 1]
    labels = [identities[row["identity"]]["label"] for row in schedule]
    assert set(labels) == {0, 1}
    longest = current = 1
    for before, after in pairwise(labels):
        current = current + 1 if before == after else 1
        longest = max(longest, current)
    assert longest <= 2


def test_sentinel_identities_do_not_reuse_prior_development_ledgers() -> None:
    manifest = _manifest()
    prior = set()
    for filename in (
        "V12_APPLICATION_OBSERVABILITY_DEVELOPMENT_EXCLUSIONS.json",
        "V12_TIMING_DEVELOPMENT_EXCLUSIONS.json",
        "V12_TIMING_DEVELOPMENT_EXCLUSIONS_V2.json",
    ):
        payload = json.loads((ROOT / filename).read_text(encoding="utf-8"))
        for key in (
            "identities",
            "excluded_observed_identities",
            "prior_functional_identities",
            "prior_methodology_identities",
            "current_methodology_test_identities",
            "local_synthetic_control_identities",
        ):
            prior.update(payload.get(key, []))
    assert set(manifest["identity_manifest"]).isdisjoint(prior)


def test_collector_contains_no_classifier_or_auc_path() -> None:
    source = (ROOT / "scripts" / "collect_v12_p10_timing_sentinel.py").read_text(
        encoding="utf-8"
    )
    assert "sklearn" not in source
    assert "roc_auc" not in source
    assert "select_on_train" not in source
    assert "matched_block_bootstrap" not in source
