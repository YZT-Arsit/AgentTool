from __future__ import annotations

from pathlib import Path

import build_v12_p10_sentinel_deployment_manifest as base

base.ENTRYPOINTS = (
    Path("scripts/collect_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/freeze_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/build_v12_p10_sentinel_resume_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_resume_deployment.py"),
    Path("scripts/build_v12_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_deployment.py"),
)


if __name__ == "__main__":
    raise SystemExit(base.main())
