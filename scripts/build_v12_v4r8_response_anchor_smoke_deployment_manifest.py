from __future__ import annotations

from pathlib import Path

import build_v12_p10_sentinel_deployment_manifest as base

base.ENTRYPOINTS = (
    Path("scripts/collect_v12_v4r8_response_anchor_smoke.py"),
    Path("scripts/analyze_v12_v4r8_response_anchor_smoke.py"),
    Path("scripts/freeze_v12_v4r8_response_anchor_smoke_analysis.py"),
    Path("scripts/freeze_v12_v4r8_response_anchor_smoke.py"),
    Path("scripts/build_v12_v4r8_response_anchor_smoke_deployment_manifest.py"),
    Path("scripts/verify_v12_v4r8_response_anchor_smoke_deployment.py"),
    Path("scripts/collect_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel_resume.py"),
    Path("scripts/build_v12_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_deployment.py"),
)
base.PROTOCOL_ARTIFACTS = (
    "V12_V4R8_RESPONSE_ANCHOR_DESIGN_FREEZE.json",
    "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CLOSURE.json",
)
base.EXTRA_PROBES = {
    "v12_timing.sentinel_smoke_v4r8": "v12_timing/sentinel_smoke_v4r8.py"
}
base.BINARIES = (
    Path("common_action_gateway_v2/bin/canonical-v12-v4r8-timing-runner"),
    Path("pir_integration/simplepir_bridge/acv-simplepir-v12-timing"),
)
base.DEPLOYMENT_SCHEMA = "AgentTool.V12V4R8ResponseAnchorSmokeDeploymentManifest/1"


if __name__ == "__main__":
    raise SystemExit(base.main())

