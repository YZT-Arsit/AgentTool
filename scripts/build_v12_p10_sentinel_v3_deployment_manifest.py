from __future__ import annotations

from pathlib import Path

import build_v12_p10_sentinel_deployment_manifest as base

base.ENTRYPOINTS = (
    Path("scripts/collect_v12_p10_timing_sentinel_v3.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel_v3.py"),
    Path("scripts/freeze_v12_p10_timing_sentinel_v3.py"),
    Path("scripts/build_v12_p10_sentinel_v3_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_v3_deployment.py"),
    Path("scripts/collect_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/build_v12_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_deployment.py"),
)
base.PROTOCOL_ARTIFACTS = (
    "V12_TIMING_STATISTICAL_PROTOCOL_V3.json",
    "V12_TIMING_OBSERVER_CONTRACT_V2.json",
    "V12_APPLICATION_OBSERVABILITY_DELTA_CANDIDATES_FREEZE.json",
    "V12_APPLICATION_OBSERVABILITY_CAPACITY_FREEZE.json",
    "V12_APPLICATION_OBSERVABILITY_GO_MANIFEST.json",
)
base.EXTRA_PROBES = {"v12_timing.sentinel_v3": "v12_timing/sentinel_v3.py"}
base.DEPLOYMENT_SCHEMA = "AgentTool.V12P10TimingSentinelV3DeploymentManifest/1"


if __name__ == "__main__":
    raise SystemExit(base.main())
