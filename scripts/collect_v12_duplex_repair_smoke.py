from __future__ import annotations

import collect_v12_p10_timing_sentinel_resume as implementation

from v12_timing.sentinel_smoke import (
    TOTAL_SESSIONS,
    build_smoke_workload,
    p10_profile,
    validate_freeze_manifest,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.build_resume_workload = build_smoke_workload
implementation.p10_profile = p10_profile
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.SESSION_SCHEMA = "AgentTool.V12DuplexRepairSmokeSession/1"
implementation.COLLECTION_SCHEMA = "AgentTool.V12DuplexRepairSmokeCollection/1"
implementation.DATASET_SCHEMA = "AgentTool.V12DuplexRepairSmokeDataset/1"
implementation.ABORT_SCHEMA = "AgentTool.V12DuplexRepairSmokeCommonAbort/1"
implementation.SESSION_RECORD_FILENAME = "duplex_repair_smoke_session_record.json"


if __name__ == "__main__":
    raise SystemExit(implementation.main())
