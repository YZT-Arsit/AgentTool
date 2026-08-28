FINAL TIMING DECISION: TIMING_NO_GO

PIR TIMING: OPEN
MULTI-ROUND TIMING: FAIL
ACTION-TYPE TIMING: OPEN
TOOL TIMING: FAIL
DUMMY HEAVY OPS: 0
RESOURCE PRIVACY: OPEN

# Timing Closure Final Report

## Executive result

The interrupted evaluation was recovered without regenerating confirmatory workloads. The native
queue/pacer preserves endpoint, count, order, and serialized size, but it does **not** close the
declared observer-boundary timing channel on the evaluated host. The final decision is
`TIMING_NO_GO`.

The decisive evidence is a frozen Tool-frequency attack over 10-observation blocks: logistic
regression reaches AUC 0.6525 (95% grouped CI 0.5677--0.7463, permutation p=0.0140) and random
forest reaches 0.6594 (0.5422--0.7712, p=0.0490). The classifier is detecting actual,
private-workload-correlated deadline slip at the socket boundary. Frame sizes remain exactly
equal and dummy heavy work remains zero.

## Recovery and holdout validity

`INTERRUPTED_RUN_RECOVERY.md` records the interruption boundary. The valid final evidence is:

- `confirmatory_final_single/`: 56 episodes and 1,344 visible slots;
- `confirmatory_final_tool_sequences/`: 30 episodes and 6,000 visible slots;
- `confirmatory_pir/`: 66 episodes and 6,600 real SimplePIR operations;
- `confirmatory_cross_session/`: preserved independent-session traces.

The earlier `confirmatory_single/` and `confirmatory_tool_sequences/` data were generated before
the NOOP bookkeeping fix and remain excluded. Public profiles and attack fields were not changed.
The continuation used development-only model fitting and group-level holdout resampling.

## PIR timing

The exact original single-query pair residual is logistic AUC 0.5272
(95% CI 0.5014--0.5535, p=0.0348) and random-forest AUC 0.5224
(0.4957--0.5468, p=0.0945).

Repeated-observation grouping does not establish a stable accumulating fingerprint:

| Observations | Logistic AUC (p) | Random-forest AUC (p) |
|---:|---:|---:|
| 10 | 0.4509 (0.0695) | 0.4332 (0.0280) |
| 50 | 0.3875 (0.0705) | 0.4139 (0.0860) |
| 100 | 0.3758 (0.1254) | 0.5216 (0.7936) |

The direction is unstable and uncertainty grows at 50/100 observations. Nevertheless, the
10-observation random-forest association and original logistic result prevent a PASS. PIR timing
is `OPEN`, not a demonstrated long-horizon linkability failure.

## Tool timing

The single-episode repeated-target test remains at chance: AUC 0.4953/0.5216 with p=0.9154/0.5920.
Rare-event attacks do not transfer above chance. Transition estimates are wide and non-significant.

Frequency leakage is different. TSEQ0 versus TSEQ2 at 10 observations passes neither the AUC nor
confidence/permutation privacy gate in either model. At 50/100 observations point estimates remain
above chance but intervals are wide because only 12 independent source episodes exist. The
10-observation result alone is sufficient to reject the timing-privacy claim for the tested
profile.

Complete statistics are in `TOOL_SEQUENCE_OBSERVATION_RESULTS.csv`,
`PIR_REPEATED_OBSERVATION_RESULTS.csv`, and `TIMING_INTERRUPTED_COMPLETION_REPORT.md`.

## Root cause

The private result queue does decouple logical completion from the decision to emit. It does not
guarantee that the emitter runs at the deadline. Provider-completion goroutines and associated
runtime/logging/encryption work share an ordinary Windows scheduler with the response pacer.
TSEQ0 has 0.56 ms mean response slip; TSEQ2 has 17.11 ms and reaches 656.96 ms. TSEQ3 reaches
28.34 ms mean and 568.46 ms maximum. These state-conditioned differences are visible in actual
socket timestamps.

Thus the earlier interpretation of the long stalls as state-independent OS noise was incorrect.
They are OS/runtime effects, but their occurrence is correlated with private workload structure.

## Properties that remain valid

- one persistent `CommonActionGateway` endpoint;
- identical request/response count and order;
- exactly 1,024 serialized bytes per request and response;
- public scheduled-deadline metadata;
- real result completion enters a private queue;
- no dummy Tool or LLM work;
- all 3,000 real Tool operations in the final sequence holdout completed exactly once;
- full regression suite: 127 passed in the documented combined local environment.

These are structural/size properties. They do not imply timing privacy.

## Limitations

- Twelve independent episodes per binary Tool-sequence comparison limit 50/100-observation power.
- The original 2,000 PIR query pairs share underlying queries; the grouped 10/50/100 analysis is
  the more conservative repeated-observation evidence.
- Primary I/O evidence is socket-boundary timestamps on loopback, not packet capture.
- Resource privacy, microarchitectural leakage, provider collusion, global traffic analysis, and
  arbitrary continuation epochs are not closed.
- All providers are controlled local synthetic emulators; no third-party system was contacted.

## Decision

`TIMING_GO` and `TIMING_CONDITIONAL_GO` are rejected for the evaluated profile because a
predefined, development-trained attack shows reproducible holdout advantage with group-aware
uncertainty and permutation controls. The appropriate result is:

> `TIMING_NO_GO`: retain the structural/size mechanism as a separate result, but do not claim
> observer-boundary timing privacy from this implementation. A future timing repair requires an
> isolated/real-time-capable pacing boundary and a new untouched confirmatory holdout.
