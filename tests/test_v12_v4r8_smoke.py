from __future__ import annotations

import json
from pathlib import Path

from v12_timing.sentinel_smoke_v4r8 import (
    TOTAL_SESSIONS,
    build_freeze_manifest,
    p10_profile,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v4r8_smoke_freeze_is_fresh_and_exact() -> None:
    prior = json.loads(
        (
            ROOT
            / "V12_V4R7_SMOKE_COLLECTOR_LATE_FRAME_CLOSURE_EVIDENCE"
            / "collection"
            / "frozen_manifest.json"
        ).read_text(encoding="utf-8")
    )
    excluded = set(prior["identity_manifest"])
    manifest = build_freeze_manifest(
        execution_source_commit="0" * 40,
        analysis_hashes={"frozen": "0" * 64},
        excluded_identities=sorted(excluded),
        exclusion_sources={"prior": "0" * 64},
    )
    validate_freeze_manifest(manifest, excluded_identities=excluded)
    assert len(manifest["identity_manifest"]) == TOTAL_SESSIONS == 640
    assert not (set(manifest["identity_manifest"]) & excluded)
    assert manifest["planned_blocks_per_coordinate"] == 64
    assert manifest["planned_train_blocks_per_coordinate"] == 32
    assert manifest["planned_eval_blocks_per_coordinate"] == 32
    assert manifest["target_train_complete_blocks"] == 30
    assert manifest["target_eval_complete_blocks"] == 30
    assert manifest["sessions_per_coordinate"] == 128
    assert manifest["physical_coordinate_count"] == 5
    assert manifest["observer_comparison_count"] == 7
    assert manifest["total_physical_sessions"] == 640
    assert manifest["response_clock"]["gateway_arrival_in_F_i"] is False
    assert manifest["closed_utility_work_reexecuted"] is False


def test_v4r8_profile_is_fixed_p10_b200() -> None:
    profile = p10_profile()
    assert profile.profile_id == "V12-TIMING-INDIST-V4R8-H50-H4500-P10-B200-PIR60"
    assert profile.total_rounds == 521
    assert profile.scheduled_lifetime_ms == 5210


def test_v4r8_analysis_entrypoint_delegates_to_runnable_layer() -> None:
    source = (
        ROOT / "scripts" / "analyze_v12_v4r8_response_anchor_smoke.py"
    ).read_text(encoding="utf-8")
    assert "status = implementation.implementation.main()" in source
    assert "status = implementation.main()" not in source
