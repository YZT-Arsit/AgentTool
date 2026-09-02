from __future__ import annotations

import json
from pathlib import Path

from v12_timing.profile import (
    DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8,
    duplex_provider_bound_p10_profile,
    duplex_response_anchor_p10_profile,
)
from v12_timing.projection import expected_raw_timing_widths

ROOT = Path(__file__).resolve().parents[1]


def test_v4r8_public_profile_changes_only_revision_and_identifier() -> None:
    old = duplex_provider_bound_p10_profile()
    new = duplex_response_anchor_p10_profile()
    assert new.profile_id == "V12-TIMING-INDIST-V4R8-H50-H4500-P10-B200-PIR60"
    assert new.timing_semantic_revision == DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8
    assert new.total_rounds == 521
    assert new.pir_resolution_opportunities == 100
    assert new.request_final_bytes == 1079
    assert new.response_final_bytes == 800
    excluded = {"profile_id", "timing_semantic_revision"}
    old_fields = old.public_schema()
    new_fields = new.public_schema()
    assert {key: value for key, value in old_fields.items() if key not in excluded} == {
        key: value for key, value in new_fields.items() if key not in excluded
    }


def test_v4r8_strengthened_observer_feature_contract_is_unchanged() -> None:
    closure = json.loads(
        (
            ROOT
            / "V12_V4R7_SMOKE_COLLECTOR_LATE_FRAME_CLOSURE_EVIDENCE"
            / "collection"
            / "frozen_manifest.json"
        ).read_text(encoding="utf-8")
    )
    widths = closure["feature_contract"]["RELAY_raw_widths"]
    assert widths == [521, 520, 521, 520, 521, 520, 521, 520, 521, 521, 521]
    assert expected_raw_timing_widths(
        "RELAY", public_r=521, public_q=100, has_relay_duplex=True
    ) == tuple(widths)
    assert sum(widths) + 12 * len(widths) + 1 == 5860
