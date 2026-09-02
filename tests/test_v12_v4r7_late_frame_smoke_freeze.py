from __future__ import annotations

import hashlib

from v12_timing.sentinel_smoke_v4r7_late_frame import (
    TOTAL_SESSIONS,
    build_freeze_manifest,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)


def test_fresh_late_frame_smoke_freeze() -> None:
    freeze = build_freeze_manifest(
        execution_source_commit="a" * 40,
        analysis_hashes={"fixture": hashlib.sha256(b"fixture").hexdigest()},
        excluded_identities=["DEV-TAD-P10-T7-OA-SENTINEL-B40000-C1"],
        exclusion_sources={"prior": hashlib.sha256(b"prior").hexdigest()},
    )
    identities = set(freeze["identity_manifest"])
    assert len(identities) == TOTAL_SESSIONS == 640
    assert all("B500" in identity for identity in identities)
    assert not any("B400" in identity for identity in identities)
    assert freeze["collector_integrity_contract"]["deadline_slip"] == "DIAGNOSTIC_ONLY"
    assert freeze["feature_contract"]["RELAY_feature_width"] == 5860
    assert freeze["feature_contract"]["REGISTRY_feature_width"] == 448
    assert freeze["statistical_protocol"]["failure_margin"] == 0.65
    validate_freeze_manifest(
        freeze, excluded_identities=["DEV-TAD-P10-T7-OA-SENTINEL-B40000-C1"]
    )

    all_complete = {identity: "COMPLETE" for identity in identities}
    completion = completion_channel(freeze, all_complete)
    assert len(completion) == 5
    assert all(row["class0_total"] == 64 for row in completion)
    assert all(row["class1_total"] == 64 for row in completion)
    assert all(row["complete_matched_blocks"] == 64 for row in completion)

    selection = select_complete_blocks(freeze, all_complete)
    for coordinate in selection.values():
        assert coordinate["SENTINEL_TRAIN"]["available_complete_blocks"] == 32
        assert coordinate["SENTINEL_TRAIN"]["target_complete_blocks"] == 30
        assert len(coordinate["SENTINEL_TRAIN"]["selected_planned_blocks"]) == 30
        assert coordinate["SENTINEL_EVAL"]["available_complete_blocks"] == 32
        assert coordinate["SENTINEL_EVAL"]["target_complete_blocks"] == 30
        assert len(coordinate["SENTINEL_EVAL"]["selected_planned_blocks"]) == 30
