from __future__ import annotations

import freeze_v12_v4r7_duplex_repair_smoke as implementation

from v12_timing.sentinel_smoke_v4r8 import build_freeze_manifest

implementation.build_freeze_manifest = build_freeze_manifest
implementation.HASHED_PATHS = (
    "common_action_gateway_v2/canonicalv9/duplex_response.go",
    "common_action_gateway_v2/canonicalv9/online.go",
    "common_action_gateway_v2/canonicalv9/runner.go",
    "v12_timing/profile.py",
    "v12_timing/classifier.py",
    "v12_timing/projection.py",
    "v12_timing/statistics.py",
    "v12_timing/collector_integrity.py",
    "v12_timing/sentinel_resume.py",
    "v12_timing/sentinel_smoke.py",
    "v12_timing/sentinel_smoke_v4r8.py",
    "scripts/collect_v12_p10_timing_sentinel_resume.py",
    "scripts/collect_v12_v4r8_response_anchor_smoke.py",
    "scripts/analyze_v12_p10_timing_sentinel_resume.py",
    "scripts/analyze_v12_duplex_repair_smoke.py",
    "scripts/analyze_v12_v4r8_response_anchor_smoke.py",
    "scripts/freeze_v12_duplex_repair_smoke_analysis.py",
    "scripts/freeze_v12_v4r8_response_anchor_smoke_analysis.py",
    "scripts/freeze_v12_v4r8_response_anchor_smoke.py",
)


if __name__ == "__main__":
    raise SystemExit(implementation.main())

