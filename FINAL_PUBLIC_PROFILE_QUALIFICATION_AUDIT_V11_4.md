# Final V11.4 public-profile qualification audit

## Decision

`ONLINE_ADMISSION_PROFILE = PASS` and `ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = YES`.

V11.4 preserved the V11.2 17/20 and V11.3 1,000-session negative evidence without reinterpretation. It classified the two independent limitations as `ONLINE_ADMISSION_HORIZON_TOO_SHORT` and `FIVE_MS_SCHEDULER_NOT_FINAL_PROFILE_QUALIFIED`. Neither is described as a privacy failure.

## Sequential qualification

Stage P froze and tested the period candidates in ascending order, selecting only the first 500/500 candidate. Stage H was instantiated only after that selection and tested admission horizons in ascending order, selecting only the first candidate passing 100/100 causal-10, 50/50 causal-20, 30/30 causal-30, and 30/30 causal-50 sessions. No two-dimensional tuning, retry, candidate extension, selected holdout, or secret-dependent session extension occurred.

Selected profile: `V11_4-STRICT-ONLINE-H50-H3000-P10`. Mixed causal families: 240/240. Final reliability: 450/450. Semantic regression: 10/10. Effective structural regression: 12/12.

Two post-selection test constructions were repaired using fresh non-holdout cases without retrying the failed arms. The original finite-horizon `H+10 ms` and V2 `H+300 ms after SESSION_READY` cases were still admitted because the latter did not account for the public 50-period start lead; both failures remain preserved. V3 waits `H + 50*Delta + 100 ms` after `SESSION_READY` and passed fail-closed. The original Agent-identity arm produced zero native outcomes; a fresh same-effect-class Agent 10 versus Agent 1 pair passed functionality and exact projections.

## Security and interpretation boundary

For a fixed public `Gamma`, the finite schedule has fixed session count, endpoint classes, HTTP/2 reuse, round count/order, OHTTP suite, sizes, and lifetime. Actions not ready before `H` fail closed. This is a finite software-profile result under the trusted-module assumption. Timing privacy remains OPEN / NOT TESTED, packet-level timing remains OPEN, and hardware TEE remains NOT_TESTED. Period qualification is scheduler reliability evidence only. No overall privacy GO is issued.

## Evidence discipline

Old V10/V10.1 selected outcomes were not observed. All V11.4 runs are non-holdout development evidence. Failures were preserved and not retried. The harness freeze exists only if every gate passed.
