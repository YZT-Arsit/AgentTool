from __future__ import annotations

import hashlib

from v12_timing.sentinel_smoke_v4r7 import (
    SMOKE_FAILURE_MARGIN,
    SMOKE_LCB_QUANTILE,
    TOTAL_SESSIONS,
    build_freeze_manifest,
    p10_profile,
    validate_freeze_manifest,
)


def _freeze():
    return build_freeze_manifest(
        execution_source_commit="a" * 40,
        analysis_hashes={"fixture": hashlib.sha256(b"fixture").hexdigest()},
        excluded_identities=["DEV-TAD-P10-T7-OA-SENTINEL-B30000-C0"],
        exclusion_sources={"prior": hashlib.sha256(b"prior").hexdigest()},
    )


def test_v4r7_smoke_profile_denominator_and_widths() -> None:
    freeze = _freeze()
    profile = p10_profile()
    assert profile.provider_completion_bound_ms == 200
    assert profile.total_rounds == 521
    assert freeze["physical_coordinate_count"] == 5
    assert freeze["observer_comparison_count"] == 7
    assert freeze["total_physical_sessions"] == TOTAL_SESSIONS == 640
    assert freeze["feature_contract"]["RELAY_feature_width"] == 5860
    assert freeze["feature_contract"]["REGISTRY_feature_width"] == 448
    validate_freeze_manifest(freeze)


def test_v4r7_smoke_identities_are_fresh_and_predeclared() -> None:
    freeze = _freeze()
    identities = set(freeze["identity_manifest"])
    assert len(identities) == 640
    assert all("B400" in identity for identity in identities)
    assert not any("B300" in identity for identity in identities)
    assert len(freeze["execution_schedule"]) == 640
    assert len(freeze["pairs"]) == 320


def test_v4r7_smoke_decision_rule_is_nonprivacy_screen() -> None:
    freeze = _freeze()
    assert SMOKE_LCB_QUANTILE == 0.05
    assert SMOKE_FAILURE_MARGIN == 0.65
    assert freeze["statistical_protocol"]["privacy_pass_authority"] is False
    assert freeze["retry_policy"] == "ZERO_RETRY_ZERO_REPLACEMENT"
    assert freeze["collection_first"] is True
