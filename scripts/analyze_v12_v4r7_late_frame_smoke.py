from __future__ import annotations

import analyze_v12_duplex_repair_smoke as implementation

from v12_timing.sentinel_smoke_v4r7_late_frame import (
    BOOTSTRAP_RESAMPLES,
    RANDOMIZATION_RESAMPLES,
    SMOKE_FAILURE_MARGIN,
    SMOKE_LCB_QUANTILE,
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.TARGET_TRAIN_COMPLETE_BLOCKS = TARGET_TRAIN_COMPLETE_BLOCKS
implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.completion_channel = completion_channel
implementation.select_complete_blocks = select_complete_blocks
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.implementation.TARGET_TRAIN_COMPLETE_BLOCKS = TARGET_TRAIN_COMPLETE_BLOCKS
implementation.implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.implementation.completion_channel = completion_channel
implementation.implementation.select_complete_blocks = select_complete_blocks
implementation.implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.implementation.SENTINEL_BOOTSTRAP_RESAMPLES = BOOTSTRAP_RESAMPLES
implementation.implementation.SENTINEL_RANDOMIZATION_RESAMPLES = RANDOMIZATION_RESAMPLES
implementation.implementation.SENTINEL_LCB_QUANTILE = SMOKE_LCB_QUANTILE
implementation.implementation.SENTINEL_EARLY_FAIL_MARGIN = SMOKE_FAILURE_MARGIN


if __name__ == "__main__":
    raise SystemExit(implementation.main())
