from __future__ import annotations

import hashlib

from v12_timing.sentinel_smoke_v4r7_late_frame import (
    TOTAL_SESSIONS,
    build_freeze_manifest,
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
