from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from v12_timing.profile import (
    DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7,
    TimingIndistinguishabilityProfile,
    duplex_provider_bound_p10_profile,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v4r7_public_capacity_is_derived_from_selected_bound() -> None:
    profile = duplex_provider_bound_p10_profile()
    assert profile.profile_id == "V12-TIMING-INDIST-V4R7-H50-H4500-P10-B200-PIR60"
    assert profile.timing_semantic_revision == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7
    assert profile.provider_completion_bound_ms == 200
    assert profile.completion_rounds == math.ceil(200 / 10) == 20
    assert profile.total_rounds == 450 + 20 + 50 + 1 == 521
    assert profile.scheduled_lifetime_ms == 5210
    assert profile.pir_resolution_opportunities == 100
    assert profile.request_final_bytes == 1079
    assert profile.response_final_bytes == 800


def test_v4r7_profile_id_and_bound_cannot_disagree() -> None:
    profile = duplex_provider_bound_p10_profile()
    with pytest.raises(ValueError, match="profile ID disagrees with public B"):
        TimingIndistinguishabilityProfile(
            **{
                **profile.__dict__,
                "profile_id": "V12-TIMING-INDIST-V4R7-H50-H4500-P10-B100-PIR60",
            }
        ).validate()


def test_bound_selection_evidence_matches_frozen_rule() -> None:
    freeze = json.loads(
        (ROOT / "V12_V4R7_PROVIDER_BOUND_SELECTION_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )
    result = json.loads(
        (
            ROOT
            / "V12_V4R7_PROVIDER_BOUND_SELECTION_EVIDENCE"
            / "PROVIDER_BOUND_SELECTION_RESULT.json"
        ).read_text(encoding="utf-8")
    )
    required = math.ceil(result["provider_end_to_end_ms"]["max"] + 50)
    selected = next(value for value in freeze["candidate_bounds_ms"] if value >= required)
    assert result["attempts"] == 10_000
    assert result["all_provider_status_ok"] is True
    assert required == result["required_bound_ms"] == 134
    assert selected == result["selected_bound_ms"] == 200


def test_v4r7_preserves_duplex_release_parameters() -> None:
    profile = duplex_provider_bound_p10_profile()
    assert profile.response_public_lag_ms == 30
    assert profile.response_preparation_lead_ms == 20
    assert profile.response_preparation_workers == 6
    assert profile.pir_commitment_lead_ms == 20
    assert profile.registry_answer_release_delay_ms == 50
    assert profile.registry_worker_lanes == 1
    assert profile.registry_max_inflight == 100
