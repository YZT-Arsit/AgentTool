from __future__ import annotations

import collect_v12_p10_timing_sentinel_resume as implementation

from v12_timing.sentinel_duplex import (
    TOTAL_SESSIONS,
    build_duplex_workload,
    p10_profile,
    validate_freeze_manifest,
)

# Bind the tested serial collection engine to the predeclared duplex campaign.
# The online runtime and workload semantics are not changed here.
implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.build_resume_workload = build_duplex_workload
implementation.p10_profile = p10_profile
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.SESSION_SCHEMA = "AgentTool.V12DuplexP10SentinelSession/1"
implementation.COLLECTION_SCHEMA = "AgentTool.V12DuplexP10SentinelCollection/1"
implementation.DATASET_SCHEMA = "AgentTool.V12DuplexP10SentinelDatasetManifest/1"
implementation.ABORT_SCHEMA = "AgentTool.V12DuplexP10SentinelCommonAbort/1"
implementation.SESSION_RECORD_FILENAME = "duplex_p10_sentinel_session_record.json"


if __name__ == "__main__":
    raise SystemExit(implementation.main())
