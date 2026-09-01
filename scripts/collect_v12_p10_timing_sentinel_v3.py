from __future__ import annotations

import collect_v12_p10_timing_sentinel_resume as implementation

from v12_timing.sentinel_v3 import (
    TOTAL_SESSIONS,
    build_v3_workload,
    validate_freeze_manifest,
)

# Reuse the already tested serial collection engine with only frozen campaign
# bindings changed. The protected runtime and workload semantics are untouched.
implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.build_resume_workload = build_v3_workload
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.SESSION_SCHEMA = "AgentTool.V12P10TimingSentinelV3Session/1"
implementation.COLLECTION_SCHEMA = "AgentTool.V12P10TimingSentinelV3Collection/1"
implementation.DATASET_SCHEMA = "AgentTool.V12P10TimingSentinelV3DatasetManifest/1"
implementation.ABORT_SCHEMA = "AgentTool.V12P10TimingSentinelV3CommonAbort/1"
implementation.SESSION_RECORD_FILENAME = "sentinel_v3_session_record.json"


if __name__ == "__main__":
    raise SystemExit(implementation.main())
