# V12 P10 timing sentinel resume closure

The fresh P10 sentinel stopped under the predeclared common-integrity rule after
2,265 identities had executed. The first common failure was a complete-session
Relay projection rejection: `Relay public slots do not match chronological
one-session order` at identity
`DEV-TAD-P10-C1_REGISTRY_RESOLUTION_PATTERN-MS-SENTINEL-B5141-C1`.

The partial campaign contained 2,258 complete and 7 failed sessions. All
failures remain recorded; no identity was retried or replaced. The original
1,204-session aborted sentinel remains sealed, and its immutable failed identity
was not reexecuted.

Because the collection did not reach all 5,040 frozen identities, no complete
block selection, completion-channel inferential diagnostic, classifier fitting,
AUC, bootstrap, or randomization analysis was performed. The ten observer
comparisons are all `NOT_RUN_DUE_COMMON_ABORT`.

Final status:

- `P10_SENTINEL = ABORTED_COMMON_INTEGRITY_FAILURE`
- `P10_SENTINEL_TIMING = NOT_EVALUABLE`
- `TIMING_PRIVACY = INCONCLUSIVE`
- `READY_FOR_P10_FULL_DEVELOPMENT = NO`

All 5,040 planned identities are permanent development exclusions. P10 full,
P20/P25 sentinel/full, timing confirmation, B4/B5, and final V12 holdout were
not run.
