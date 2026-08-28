# Interrupted Run Recovery

Recovery audit date: 2026-08-27 (America/Los_Angeles)

This manifest establishes the evidentiary boundary of the interrupted timing-closure run. No
confirmatory workload was regenerated during this audit. File timestamps, record counts, raw
logs, and the frozen public configuration were inspected before any additional analysis.

## Completed experiments

| Experiment | Preserved artifact | Completion evidence | Status |
|---|---|---|---|
| Fresh single-action confirmatory holdout | `results_timing_closure/confirmatory_final_single/` | 10 files; traces written 18:53:03--18:54:15; 56 ground-truth episodes, 1,344 host-visible slots, 2,688 socket-boundary events | COMPLETE |
| Fresh Tool-sequence confirmatory holdout | `results_timing_closure/confirmatory_final_tool_sequences/` | 10 files; traces written 18:54:15--18:55:17; 30 ground-truth episodes, 6,000 host-visible slots, 12,000 socket-boundary events | COMPLETE |
| Real SimplePIR confirmatory holdout | `results_timing_closure/confirmatory_pir/` | 9 files; traces written 18:45:21--18:45:58; 6,600 server-visible queries and 6,600 client records; all recoveries previously verified | COMPLETE |
| Cross-session PIR holdout | `results_timing_closure/confirmatory_cross_session/` | 65 files; traces written 18:45:58--18:46:07 | COMPLETE |
| Initial statistical pass | `ACTION_TIMING_RESULTS.csv`, `TOOL_TIMING_RESULTS.csv`, `PIR_FIXED_SCHEDULE_RESULTS.csv`, `MULTIROUND_TIMING_RESULTS.csv`, `CROSS_SESSION_TIMING_RESULTS.csv`, `TIMING_CONFIRMATORY_HOLDOUT_RESULTS.csv`, `TIMING_OVERHEAD_RESULTS.csv` | All written 18:57:44--18:57:45 after the raw confirmatory traces | COMPLETE FOR THE METRICS PRESENT |
| Native implementation checks | `tests/test_timing_closure.py` | Seven timing-closure tests passed before interruption | COMPLETE, NARROW TEST SET ONLY |

Preserved host/server trace SHA-256 values at recovery were:

- final single-action host trace: `4288801453A277E2C4C1AEA59487409BE48419C46D163421A905AAAE96FBAB5C`;
- final Tool-sequence host trace: `E3A7EC601134E64B12C9FDBACF6EA746E46337E2328B0358586646B503183EEA`;
- confirmatory PIR server trace: `B4009BBB005112C9C25E83957EEAB853D7835F5BE8B7EBCB31C0409D8048655A`.

The public parameters remain frozen in
`results_timing_closure/confirmatory_frozen_configuration.json`: `R_pir=100`,
`Delta_pir=5 ms`, I/O profiles `STANDARD=(R=24, Delta=50 ms, B=1024)` and
`LONG_SEQUENCE=(R=200, Delta=10 ms, B=1024)`. The continuation must not alter
these values or the existing attack-feature definitions.

## Incomplete experiments and analyses

1. PIR pairwise residual analysis aggregated over exactly 10, 50, and 100 observations,
   including holdout AUC, confidence interval, grouped permutation test, and an assessment of
   whether the earlier single-observation residual reproduces.
2. Tool-sequence frequency, rare-event, and transition analyses at 10/50/100-observation
   aggregation, with uncertainty and permutations grouped by source episode. The existing
   repeated-target test is complete at its frozen granularity; no unmeasured repeated Tool
   sequence may be fabricated.
3. Reconciliation of the supplemental statistics with the timing security matrix and final
   report.
4. The full repository regression suite after the native timing-closure changes.

## Valid artifacts

- All raw files under `confirmatory_final_single/`, `confirmatory_final_tool_sequences/`,
  `confirmatory_pir/`, and `confirmatory_cross_session/`.
- The corresponding development traces, used only to fit the frozen attacks.
- `results_timing_closure/confirmatory_frozen_configuration.json`.
- The first-generation result CSVs, but only for the individual metrics and sample sizes that
  they actually contain.
- Local FAST/MEDIUM/SLOW/VERY_SLOW/JITTERED provider-emulator measurements. They are local
  workload evidence and are not evidence about third-party services.

## Partial or superseded artifacts

- `results_timing_closure/confirmatory_single/` and
  `results_timing_closure/confirmatory_tool_sequences/` are preserved but superseded. They were
  generated before the NOOP bookkeeping defect was corrected and MUST NOT be used as
  confirmatory evidence.
- `TIMING_CLOSURE_FINAL_REPORT.md` and `TIMING_SECURITY_MATRIX.md` are draft analyses of the
  completed first pass. They predate the required observation-aggregation analyses and the full
  regression run.
- Smoke/test output directories, if present, are implementation diagnostics rather than
  confirmatory evidence.

## Results that must not yet be cited

- Any final `TIMING_GO`, `TIMING_CONDITIONAL_GO`, or `TIMING_NO_GO` decision from the interrupted
  run.
- Any claim that the PIR AUC 0.527 residual is persistent under repeated observation. The point
  estimate was statistically significant in one single-query logistic-regression analysis, but
  aggregation at 10/50/100 observations had not been performed.
- Any claim that high Tool-sequence point estimates demonstrate leakage. The frozen holdout has
  only six episodes per sequence class; the existing confidence intervals are wide and the
  permutation tests are not significant.
- Any claim that the complete repository regression suite passed after the timing changes.

## Predeclared continuation analysis

The continuation uses only preserved traces. Models remain logistic regression and random
forest with the existing host-visible timing features. For PIR and Tool sequences, consecutive
non-overlapping blocks of 10, 50, or 100 observations are summarized with the same timing
statistics already used by the frozen attacks. Development artifacts fit the classifier;
`confirmatory_*` artifacts remain test-only. Confidence resampling and label permutation are
performed at the source-episode or source-episode-pair level so multiple blocks from one episode
are not treated as independent confirmatory repetitions. No feature, public profile, trace, or
implementation will be tuned from the resulting holdout scores.

## Recovery completion

The predeclared continuation completed without regenerating a workload or changing a raw trace.
It produced `PIR_REPEATED_OBSERVATION_RESULTS.csv` and
`TOOL_SEQUENCE_OBSERVATION_RESULTS.csv`. The full repository suite was then run with the
documented local OpenAI Agents SDK, Microsoft Agent Framework, and scientific-Python paths:
`127 passed`. An initial incomplete-path invocation produced `120 passed, 7 failed` solely
because `agents` was absent from that interpreter's import path; rerunning in the documented
combined local environment resolved all seven collection/runtime failures without a source
change.
