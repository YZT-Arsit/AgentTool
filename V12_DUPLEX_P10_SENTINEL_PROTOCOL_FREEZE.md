# V12 Duplex P10 Sentinel Protocol Freeze

This pre-execution protocol is based on duplex evidence commit
`bf499d5e56507eb069d4998a2851cfaa23ec7fc6`. It authorizes only the fresh
P10 duplex sentinel, conditional on a passing candidate-specific audit of the
immutable P10 16/16 functional records and a passing deployment-integrity
gate.

P20 remains `FAIL_UNRESOLVED` because
`DEV-DTVR-V4R5-P20-MS-CACHE_REUSE_30-007` returned 13 of 30 expected
operations; its root cause is not established. P25 remains `NOT_TESTED`.
Neither profile is authorized here, and the P20 observation does not change
P10 eligibility unless a common runtime defect is mechanically established.

The P10 profile is V4R5, H=4500 ms, Delta=10 ms, R=506, M=50, PIR60,
epoch6000, Q=100, with 1079-byte requests and 800-byte responses. The frozen
sentinel has eight physical task/framework coordinates, 315 matched blocks per
coordinate (189 TRAIN and 126 EVAL), and 5,040 fresh one-use identities. The
analysis selects the first 180 complete TRAIN and first 120 complete EVAL
blocks using pre-frozen priorities.

The Relay application observer receives only the four application-boundary
timelines plus public session/slot/profile and fixed-size metadata. The Relay
feature width is 5,695. The Registry timing-only feature width is 448. Neither
view contains private semantics, failure status, block identity, execution
ordinal, or diagnostics.

Collection closes and is hash-audited before any classifier fit, AUC,
bootstrap, or randomization calculation. Analysis then uses the unchanged
V3.1 train-only four-model procedure, one TRAIN-selected EVAL model, uint64 to
uint32 estimator-seed normalization, 10,000 complete-block bootstrap
resamples, and the predeclared `LCB99.5 > 0.55` early-failure rule. The
sentinel cannot establish privacy. P10 full development, P20/P25, timing
confirmation, and final holdout remain unauthorized.
