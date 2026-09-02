# V12 P10 timing leakage-source attribution protocol

Status: **POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC**.

This diagnostic is frozen after the immutable P10 sentinel result at
`558c97bd5ca8bb9123382800cb73eb410cab6342`. It does not replace the original
`EARLY_TIMING_DISTINGUISHABILITY` verdict (6/10 early failures), authorize a
privacy claim, or alter V3.1.

The input is exactly the closed 5,040-identity dataset: 5,025 complete and 15
failed sessions, with the already frozen 180 TRAIN and 120 EVAL complete
matched blocks per physical coordinate. No identity, split, priority, label,
projection, or block selection may change.

## Frozen partitions

Relay partitions are R1+R2 (request only), R3+R4 (response only), R5
(slot-paired latency only), R1-R4 (request plus response), and the exact
original R1-R6 representation (all). Registry partitions are request
arrival/gaps, response-send, query-response latency, request plus response,
and the exact original representation.

Every subset is a direct slice of the frozen feature vector. No new feature,
slot selection, lag search, dimensionality reduction, or hyperparameter search
is permitted. The ALL-family row is copied from the immutable decisive V3.1
result, not refitted.

## Statistical machinery

The four frozen model families, five-fold block-respecting TRAIN CV,
TRAIN-only model selection and orientation, 180/120 block denominators, and
10,000 complete-EVAL-block bootstrap are unchanged. The existing
LCB99.5 > 0.55 boundary is reused only to make a descriptive attribution; no
new decision rule or official P10 verdict is created.

Observer-only family results are written before any private mechanism
correlation is performed. Private REAL/NOOP/WAIT/RESULT or provider records
may be used only afterward and never enter a classifier feature.

Protected runtime diff: **NONE**. New protected sessions: **0**. P20 and P25:
**NOT RUN**.
