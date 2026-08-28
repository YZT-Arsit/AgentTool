# Interrupted Timing Analysis Completion

## Decision

`TIMING_NO_GO`

This decision applies to the claimed timing-privacy profile on the evaluated general-purpose
Windows/loopback deployment. Structural endpoint/count/order privacy and exact 1,024-byte frame
equality remain valid, but the actual release cadence is distinguishable under a frozen Tool
frequency attack.

## Evidentiary discipline

- No confirmatory experiment was rerun.
- `R_pir`, `Delta_pir`, `R_io`, `Delta_io`, and `B` were not changed.
- Models and host-visible timing fields were not selected from the final holdout.
- Development traces fit the models; `confirmatory_final_*` and `confirmatory_pir` were test-only.
- Blocks from one episode were treated as correlated. Confidence intervals and permutations
  resampled whole source episodes (or PIR source-episode pairs), not individual blocks.
- The old pre-NOOP-fix `confirmatory_single/` and `confirmatory_tool_sequences/` artifacts were
  excluded.

## PIR pairwise residual

The exact frozen single-query result is:

| Observations | Model | AUC | 95% CI | Permutation p | Interpretation |
|---:|---|---:|---:|---:|---|
| 1 | Logistic regression | 0.5272 | 0.5014--0.5535 | 0.0348 | Small positive residual in the original correlated-pair analysis |
| 1 | Random forest | 0.5224 | 0.4957--0.5468 | 0.0945 | Not significant |
| 10 | Logistic regression | 0.4509 | 0.4076--0.4954 | 0.0695 | Inverse direction; not significant at 0.05 |
| 10 | Random forest | 0.4332 | 0.3825--0.4874 | 0.0280 | Significant inverse-direction dependence |
| 50 | Logistic regression | 0.3875 | 0.2804--0.5002 | 0.0705 | Non-significant, grouped uncertainty |
| 50 | Random forest | 0.4139 | 0.3127--0.5212 | 0.0860 | Non-significant, grouped uncertainty |
| 100 | Logistic regression | 0.3758 | 0.1898--0.5818 | 0.1254 | Wide uncertainty |
| 100 | Random forest | 0.5216 | 0.3607--0.6795 | 0.7936 | Wide uncertainty |

Permutation AUC means for the grouped tests are 0.5000--0.5008. The 10/50/100
tests use 66 independent source-episode-pair groups; their sample counts are 660, 132, and 66
matching-position block pairs. Below-0.5 AUCs are not relabeled as privacy successes: an inverse
direction is still association, but the direction learned on development did not transfer.

There is no monotonic strengthening from 10 to 50 to 100 observations and no two-model,
same-direction confirmation. Thus the exact 0.527 point estimate is **not established as a
stable accumulating PIR fingerprint**. PIR timing nevertheless remains `OPEN`, because the
10-observation random-forest group test rejects independence and the original single-query
logistic test was significant.

## Tool sequence analyses

The frozen final holdout has six episodes per sequence class. At aggregation 10, 50, and 100,
each binary test therefore has only 12 independent episode groups, even though 10-observation
analysis yields 120 correlated block samples.

### Frequency: TSEQ0 versus TSEQ2

| Observations | Logistic AUC (95% CI, p) | Random-forest AUC (95% CI, p) |
|---:|---|---|
| 10 | 0.6525 (0.5677--0.7463, 0.0140) | 0.6594 (0.5422--0.7712, 0.0490) |
| 50 | 0.6042 (0.3143--0.8673, 0.4508) | 0.5972 (0.3403--0.8287, 0.4578) |
| 100 | 0.5833 (0.2000--0.9143, 0.6847) | 0.6250 (0.2500--0.9571, 0.5072) |

The 10-observation result is reproducible across both frozen model families, both confidence
intervals exclude chance, and both group-permutation tests meet p <= 0.05. This is genuine
residual timing leakage in this holdout. The 50/100 estimates are not independently conclusive;
their intervals are wide because the number of episodes remains 12.

### Rare event: TSEQ0 versus TSEQ1

No aggregation shows transferable above-chance classification. At 10 observations the AUCs are
0.4286 (p=0.3083) and 0.4883 (p=0.8371). At 50 and 100 observations the estimates remain below
chance with intervals touching or spanning 0.5. This attack is not evidence of rare-event
leakage.

### Transition: TSEQ3 versus TSEQ4

At 10 observations the AUCs are 0.5992 (95% CI 0.4694--0.7271, p=0.1579) and 0.5417
(0.4278--0.6506, p=0.5007). The 50/100 estimates are high for some models but have very wide
intervals and non-significant permutations. These are high point estimates under small-sample
uncertainty, not a reproducible transition result.

### Repeated target

The already-completed frozen Tool-pair test remains valid: logistic AUC 0.4953
(95% CI 0.4294--0.5647, p=0.9154) and random-forest AUC 0.5216
(0.4479--0.5998, p=0.5920), based on 276 test pairs. It shows no repeated-target advantage at
that measured granularity. The preserved sequence workload does not contain enough independent
homogeneous 10/50/100-round Tool episodes to manufacture a second repeated-target aggregation;
none was fabricated.

## Deadline-slip cause

Actual receiver-visible frame sizes remain equal. Actual release times do not. Across the first
100 real Tool slots, mean Gateway response slip is 0.56 ms for TSEQ0 and 17.11 ms for TSEQ2;
TSEQ2 reaches 656.96 ms maximum slip. TSEQ3 reaches 28.34 ms mean and 568.46 ms maximum. The
native Gateway runs one goroutine per real provider completion on the same ordinary OS scheduler
as the response pacer. Completion wakeups, JSON logging, encryption/randomness work, Go runtime
scheduling, and system contention can therefore delay the supposedly public release slot in a
private-workload-correlated way.

This is observer-boundary leakage: it is present in actual socket send/receive timestamps. It is
not a logical payload-size artifact and cannot be dismissed as a high but imprecise classifier
estimate.

## Correctness and environment

- Authorization/effect behavior: preserved.
- Dummy heavy operations: 0.
- Real Tool operations in the final sequence holdout: 3,000, each once.
- Fixed endpoint and frame size: pass.
- Full local regression suite: 127 passed.
- Third-party targets: none used; provider classes are local synthetic emulators.

## Final interpretation

The fixed queue and deadline abstraction is useful but insufficient on this deployment because
the pacer does not have isolated or real-time scheduling guarantees. The result is
`TIMING_NO_GO`, not a claim that timing privacy is impossible in principle. Any future
confirmation would require an independently engineered isolation/real-time boundary and a fresh,
untouched holdout; the preserved holdout may not be reused to tune that repair.
