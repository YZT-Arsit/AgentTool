from __future__ import annotations

import collect_v12_p10_timing_sentinel_resume as implementation

from v12_timing.sentinel_smoke_v4r7_late_frame import (
    TOTAL_SESSIONS,
    build_smoke_workload,
    p10_profile,
    validate_freeze_manifest,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.build_resume_workload = build_smoke_workload
implementation.p10_profile = p10_profile
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.SESSION_SCHEMA = "AgentTool.V12V4R7LateFrameCollectorSmokeSession/1"
implementation.COLLECTION_SCHEMA = "AgentTool.V12V4R7LateFrameCollectorSmokeCollection/1"
implementation.DATASET_SCHEMA = "AgentTool.V12V4R7LateFrameCollectorSmokeDataset/1"
implementation.ABORT_SCHEMA = "AgentTool.V12V4R7LateFrameCollectorSmokeCommonAbort/1"
implementation.SESSION_RECORD_FILENAME = "v4r7_late_frame_smoke_session.json"


if __name__ == "__main__":
    raise SystemExit(implementation.main())
