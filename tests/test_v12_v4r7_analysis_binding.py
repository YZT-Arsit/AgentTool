from __future__ import annotations

import copy

import pytest

from scripts.freeze_v12_v4r7_late_frame_analysis_binding import (
    BOUND_SENTINEL_SMOKE_SHA256,
    COLLECTION_SOURCE_COMMIT,
    ORIGINAL_SENTINEL_SMOKE_SHA256,
    build_analysis_authority,
    payload_sha256,
)


def fixture_manifest() -> dict[str, object]:
    return {
        "execution_source_commit": COLLECTION_SOURCE_COMMIT,
        "analysis_hashes": {
            "v12_timing/sentinel_smoke.py": ORIGINAL_SENTINEL_SMOKE_SHA256,
            "v12_timing/projection.py": "projection-frozen",
            "v12_timing/classifier.py": "classifier-frozen",
            "v12_timing/statistics.py": "statistics-frozen",
        },
        "payload_sha256": "old-payload",
    }


def test_analysis_authority_changes_only_binding_source_and_commit() -> None:
    assert len(ORIGINAL_SENTINEL_SMOKE_SHA256) == 64
    assert len(BOUND_SENTINEL_SMOKE_SHA256) == 64
    original = fixture_manifest()
    preserved = copy.deepcopy(original)
    authority = build_analysis_authority(original, analysis_source_commit="a" * 40)
    assert original == preserved
    assert authority["execution_source_commit"] == "a" * 40
    assert (
        authority["analysis_hashes"]["v12_timing/sentinel_smoke.py"]
        == BOUND_SENTINEL_SMOKE_SHA256
    )
    for relative in (
        "v12_timing/projection.py",
        "v12_timing/classifier.py",
        "v12_timing/statistics.py",
    ):
        assert authority["analysis_hashes"][relative] == original["analysis_hashes"][relative]
    assert authority["payload_sha256"] == payload_sha256(authority)


def test_analysis_authority_rejects_unexpected_original_binding() -> None:
    original = fixture_manifest()
    original["analysis_hashes"]["v12_timing/sentinel_smoke.py"] = "unexpected"
    with pytest.raises(ValueError, match="unexpected original"):
        build_analysis_authority(original, analysis_source_commit="a" * 40)
