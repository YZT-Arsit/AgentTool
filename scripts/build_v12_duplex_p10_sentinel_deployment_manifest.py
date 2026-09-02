from __future__ import annotations

from pathlib import Path

import build_v12_p10_sentinel_deployment_manifest as base

base.ENTRYPOINTS = (
    Path("scripts/collect_v12_duplex_p10_sentinel.py"),
    Path("scripts/analyze_v12_duplex_p10_sentinel.py"),
    Path("scripts/freeze_v12_duplex_p10_analysis.py"),
    Path("scripts/freeze_v12_duplex_p10_sentinel.py"),
    Path("scripts/build_v12_duplex_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_duplex_p10_sentinel_deployment.py"),
    Path("scripts/collect_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/build_v12_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_deployment.py"),
)
base.PROTOCOL_ARTIFACTS = (
    "V12_DUPLEX_P10_SENTINEL_PROTOCOL_FREEZE.json",
    "V12_DUPLEX_TIMING_VIRTUALIZATION_DESIGN_FREEZE.json",
    "V12_TIMING_OBSERVER_CONTRACT_V2.json",
)
base.EXTRA_PROBES = {"v12_timing.sentinel_duplex": "v12_timing/sentinel_duplex.py"}
base.BINARIES = (
    Path("common_action_gateway_v2/bin/canonical-v12-duplex-timing-runner"),
    Path("pir_integration/simplepir_bridge/acv-simplepir-v12-timing"),
)
base.DEPLOYMENT_SCHEMA = "AgentTool.V12DuplexP10SentinelDeploymentManifest/1"


if __name__ == "__main__":
    raise SystemExit(base.main())
