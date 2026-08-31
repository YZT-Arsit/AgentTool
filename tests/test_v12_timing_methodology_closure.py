from __future__ import annotations

import numpy as np
import pytest

from v12_timing import classifier
from v12_timing.classifier import fit_train_predict_eval
from v12_timing.matched_tasks import (
    FRAMEWORKS, PRIMARY_TASKS, TASK_DEFINITIONS, T1_PRIMARY_ISOLATION,
    build_matched_pair, verify_pair_public_profile_equality,
)
from v12_timing.matrix import TASKS as OLD_TASKS, _labels
from v12_timing.profile import causal_horizon_candidate_profiles
from v12_timing.projection import (
    INTERNAL_PRIVATE_STATE, PARTIAL_TIMING_VIEW, REGISTRY_SOURCE_PROVENANCE, TIMING_ONLY_VIEW,
    expected_raw_timing_widths, observer_contract, registry_timing_projection,
    relay_timing_projection, timing_feature_vector, validate_projection_schema,
)
from v12_timing.statistics import (
    bootstrap_family_auc, deterministic_block_split, family_auc,
    distinguishability_auc, paired_label_randomization, partition_indices, resample_complete_blocks,
    validate_matched_blocks,
)


def _gf2_rank(matrix: np.ndarray) -> int:
    value = matrix.copy() % 2
    rank = 0
    for column in range(value.shape[1]):
        pivots = np.flatnonzero(value[rank:, column])
        if not len(pivots):
            continue
        pivot = rank + int(pivots[0])
        value[[rank, pivot]] = value[[pivot, rank]]
        for row in range(value.shape[0]):
            if row != rank and value[row, column]:
                value[row] ^= value[rank]
        rank += 1
    return rank


def _relay_rows(count: int, *, private_value: str = "secret") -> list[dict[str, object]]:
    return [{
        "profile_id": "profile", "session": 1, "round": index + 1,
        "request_length": 1079, "response_length": 800,
        "request_observed_ns": 1_000_000 + index * 10_000,
        "response_observed_ns": 1_001_000 + index * 10_000,
        "new_private_field": private_value, "operation_id": private_value,
    } for index in range(count)]


def _registry_rows(count: int, *, add_send: bool = False) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        row: dict[str, object] = {
            "ordinal": index, "query_bytes": 2020, "answer_bytes": 6592,
            "query_rows": 1000, "query_cols": 1,
            "request_arrival_ns": 2_000_000 + index * 60_000,
            "answer_ready_ns": 2_000_500 + index * 60_000,
            "executor": "private", "request_kind": "private", "renamed_secret": "private",
        }
        if add_send:
            row["response_send_ns"] = 2_001_000 + index * 60_000
        rows.append(row)
    return rows


def test_old_16_row_matrix_has_four_bit_rank_and_nonlinear_aliases() -> None:
    matrix = np.asarray([list(_labels(row).values()) for row in range(16)], dtype=np.int64)
    assert matrix.shape == (16, len(OLD_TASKS))
    assert _gf2_rank(matrix) == 4
    assert np.array_equal(matrix[:, 0] ^ matrix[:, 1], matrix[:, 2])
    assert np.array_equal(matrix[:, 0] ^ matrix[:, 3], matrix[:, 4])


def test_task_pairs_are_framework_independent_and_public_profile_equal() -> None:
    profile = causal_horizon_candidate_profiles()[0]
    for task in PRIMARY_TASKS:
        pairs = [build_matched_pair(task, framework, block=7, stage="CONTROL", delta_ms=10,
                                    seed_hex="freeze") for framework in FRAMEWORKS]
        assert {pair.framework for pair in pairs} == set(FRAMEWORKS)
        assert all({member.label for member in pair.members} == {0, 1} for pair in pairs)
        assert all(verify_pair_public_profile_equality(pair, {0: profile, 1: profile}) for pair in pairs)
    assert T1_PRIMARY_ISOLATION == "NOT_FEASIBLE"
    assert {task for task, spec in TASK_DEFINITIONS.items() if spec.estimand == "COMPOSITE"} == {"T7", "T8", "T10"}


def test_pair_order_randomization_is_deterministic_and_not_framework_encoded() -> None:
    for framework in FRAMEWORKS:
        first_labels = [build_matched_pair("T2", framework, block=block, stage="CONTROL",
                                           delta_ms=10, seed_hex="freeze").members[0].label
                        for block in range(32)]
        repeated = [build_matched_pair("T2", framework, block=block, stage="CONTROL",
                                       delta_ms=10, seed_hex="freeze").members[0].label
                    for block in range(32)]
        assert first_labels == repeated
        assert set(first_labels) == {0, 1}


def test_protected_fixed_transcript_vector_dimensions_are_public_r_and_q() -> None:
    for profile in causal_horizon_candidate_profiles()[:1]:
        relay = relay_timing_projection({"public_relay_events": _relay_rows(profile.total_rounds)},
                                        expected_rounds=profile.total_rounds)
        registry = registry_timing_projection(_registry_rows(profile.pir_resolution_opportunities),
                                              profile_id=profile.profile_id,
                                              pir_period_ms=profile.pir_resolution_period_ms,
                                              opportunities=profile.pir_resolution_opportunities)
        relay_widths = expected_raw_timing_widths("RELAY", public_r=profile.total_rounds,
                                                 public_q=profile.pir_resolution_opportunities)
        registry_widths = expected_raw_timing_widths("REGISTRY", public_r=profile.total_rounds,
                                                    public_q=profile.pir_resolution_opportunities)
        assert len(timing_feature_vector(relay, raw_widths=relay_widths)) == sum(relay_widths) + 12 * len(relay_widths) + 1
        assert len(timing_feature_vector(registry, raw_widths=registry_widths)) == sum(registry_widths) + 12 * len(registry_widths) + 1


def test_observer_allowlist_and_derived_provenance_exclude_new_private_fields() -> None:
    relay = relay_timing_projection({"public_relay_events": _relay_rows(3)})
    registry = registry_timing_projection(_registry_rows(3), profile_id="profile", pir_period_ms=60, opportunities=3)
    assert relay["view"] == registry["view"] == PARTIAL_TIMING_VIEW
    encoded = repr((relay, registry))
    assert "secret" not in encoded and "renamed_secret" not in encoded and "executor" not in encoded
    contract = observer_contract()
    assert contract["registry_source_fields"]["answer_ready_ns"] == INTERNAL_PRIVATE_STATE
    assert all(value in contract["allowed_provenance"] for value in contract["relay_projection_fields"].values())
    assert all(value in contract["allowed_provenance"] for value in contract["registry_projection_fields"].values())
    with pytest.raises(AssertionError):
        validate_projection_schema(dict(relay, newly_named_private_field="value"))


def test_registry_uses_only_application_send_timestamp_and_never_answer_ready() -> None:
    without_send = registry_timing_projection(_registry_rows(3), profile_id="p", pir_period_ms=60, opportunities=3)
    with_send = registry_timing_projection(_registry_rows(3, add_send=True), profile_id="p", pir_period_ms=60, opportunities=3)
    assert "query_response_ns" not in without_send
    assert with_send["query_response_ns"] == [1000, 1000, 1000]
    assert with_send["view"] == TIMING_ONLY_VIEW
    with pytest.raises(ValueError, match="complete Registry"):
        registry_timing_projection(_registry_rows(3), profile_id="p", pir_period_ms=60, opportunities=3,
                                   require_complete_application_timing=True)
    assert REGISTRY_SOURCE_PROVENANCE["answer_ready_ns"] == INTERNAL_PRIVATE_STATE


def test_relay_uses_only_explicit_application_send_timestamp() -> None:
    rows = _relay_rows(3)
    without_send = relay_timing_projection({"public_relay_events": rows})
    assert "request_response_ns" not in without_send
    for index, row in enumerate(rows):
        row["response_send_ns"] = 1_001_000 + index * 10_000
    with_send = relay_timing_projection({"public_relay_events": rows})
    assert with_send["request_response_ns"] == [1000, 1000, 1000]
    assert with_send["view"] == TIMING_ONLY_VIEW
    with pytest.raises(ValueError, match="complete Relay"):
        relay_timing_projection({"public_relay_events": _relay_rows(3)},
                                require_complete_application_timing=True)


def test_relay_requires_one_session_and_chronological_public_slots() -> None:
    rows = _relay_rows(3)
    rows[0], rows[1] = rows[1], rows[0]
    projection = relay_timing_projection({"public_relay_events": rows})
    assert projection["public_slot_order"] == [1, 2, 3]
    rows = _relay_rows(3)
    rows[1]["session"] = 2
    with pytest.raises(ValueError, match="exactly one"):
        relay_timing_projection({"public_relay_events": rows})
    rows = _relay_rows(3)
    rows[1]["round"] = 3
    with pytest.raises(ValueError, match="chronological"):
        relay_timing_projection({"public_relay_events": rows})


def test_block_split_keeps_pairs_whole_and_disjoint() -> None:
    labels = [value for _ in range(10) for value in (0, 1)]
    blocks = [block for block in range(10) for _ in (0, 1)]
    validate_matched_blocks(labels, blocks)
    split = deterministic_block_split(blocks, seed_hex="split")
    train, evaluation = partition_indices(blocks, split)
    assert len(train) == 12 and len(evaluation) == 8
    assert set(np.asarray(blocks)[train]).isdisjoint(set(np.asarray(blocks)[evaluation]))
    assert all(np.count_nonzero(np.asarray(blocks)[train] == block) == 2 for block in split.train_blocks)


def test_fit_protocol_never_passes_eval_rows_to_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    fitted: list[np.ndarray] = []

    class RecordingModel:
        def fit(self, values: np.ndarray, labels: np.ndarray) -> "RecordingModel":
            fitted.append(values.copy())
            return self

        def predict_proba(self, values: np.ndarray) -> np.ndarray:
            return np.column_stack((np.full(len(values), .5), np.full(len(values), .5)))

    monkeypatch.setattr(classifier, "frozen_models", lambda seed: {name: RecordingModel() for name in classifier.MODEL_NAMES})
    blocks = [block for block in range(10) for _ in (0, 1)]
    labels = [value for _ in range(10) for value in (0, 1)]
    vectors = [[float(index), float(index % 2)] for index in range(20)]
    split = deterministic_block_split(blocks, seed_hex="fit")
    train, evaluation = partition_indices(blocks, split)
    result = fit_train_predict_eval(vectors, labels, blocks, split, seed=1)
    expected = np.asarray(vectors)[train]
    assert all(np.array_equal(value, expected) for value in fitted)
    assert result.eval_sample_count == len(evaluation)


def test_complete_pair_resampling_family_max_and_randomization() -> None:
    labels = np.asarray([0, 1, 0, 1, 0, 1])
    blocks = np.asarray([0, 0, 1, 1, 2, 2])
    members = validate_matched_blocks(labels, blocks)
    sample = resample_complete_blocks(members, np.random.default_rng(7))
    assert len(sample) == len(labels)
    for offset in range(0, len(sample), 2):
        assert sorted(labels[sample[offset:offset + 2]].tolist()) == [0, 1]
    predictions = {"a": [.1, .9, .2, .8, .3, .7], "b": [.9, .1, .8, .2, .7, .3]}
    maximum, components = family_auc(labels, predictions)
    assert maximum == max(distinguishability_auc(value) for value in components.values()) == 1.0
    result = bootstrap_family_auc(labels, predictions, blocks, seed=9, resamples=50)
    assert result["model_family_distinguishability_auc"] == 1.0 and result["refit_inside_bootstrap"] is False
    randomized = paired_label_randomization(labels, blocks, seed=4)
    for indices in members.values():
        assert sorted(randomized[indices].tolist()) == [0, 1]


@pytest.mark.parametrize(("raw", "expected"), ((0.40, 0.60), (0.50, 0.50), (0.80, 0.80)))
def test_auc_orientation_erratum(raw: float, expected: float) -> None:
    assert distinguishability_auc(raw) == pytest.approx(expected)
