# Final V11.3 online profile-closure audit

## Decision

`ONLINE_ADMISSION_PROFILE = FAIL` and `ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = NO`.

The development phase correctly separated maximum real operations (`M=50`) from admission opportunities (`A`). It then executed all five predeclared candidates and all 1,000 required strictly causal sessions. No candidate passed every stratum. The largest, A=300 (1,500 ms admission horizon; 361 total rounds; 1,805 ms scheduled lifetime), completed 180/200 sessions overall but 0/20 fifty-action sessions. Consequently no public profile was selected and every post-selection gate remained unexecuted.

## Root cause and evidence

The V11.2 17/20 negative result remains immutable. V11.3 confirms the broader root cause class `ONLINE_PROFILE_ADMISSION_HORIZON_TOO_SHORT`: deeper online trajectories require more public admission opportunities than the predeclared set provides. Across qualification, resolved-not-admitted events totaled 2625. Qualification also observed 3 scheduler misses across 1,000 sessions; these are independently disqualifying and were not hidden. Aggregate profile overflow=0, dummy heavy operations=0, and silent committed-result loss=0.

## Selection discipline

Candidates and the smallest-passing rule were frozen before execution. No seed search, candidate extension, retry of failed runs, holdout inspection, V10/V10.1 selected execution, secret-dependent session extension, second session, or public-profile mutation occurred. The result does not authorize adding A=400 after inspection; doing so would require a new explicitly predeclared development phase.

## What remains established

V11.2 online ingress, one public session, live delivery, dynamic SimplePIR, Agent-as-Tool, and OpenAI handoff remain preserved development evidence. V11.3 does not invalidate those mechanisms. It shows only that the current predeclared online public-profile family is not capacious enough to close the full 50-operation strictly causal scope.

## Claims not made

Timing privacy remains OPEN / NOT TESTED; packet-level timing remains OPEN; hardware TEE remains NOT_TESTED. No overall privacy GO is issued. No V11.3 harness freeze is created because the completion gate did not pass.

## Evidence integrity

Qualification host and binary provenance are in `results_v11_3_development/qualification_host.json`. The machine-readable 1,000-row result is `CAUSAL_DEPTH_QUALIFICATION_V11_3.csv`. Raw per-session evidence remains on the authorized Linux qualification host and is indexed by the transferred hash manifest.
