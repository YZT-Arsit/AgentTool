# Stage 12 final report — historical, invocation design superseded

The private-dispatch/ORAM-backed invocation portions are rejected and are not
part of the active control-virtualization design.

## Executive decision

`C — TIMING/SIZE LIVE DEFENSE FAILS`

M3 survives real native approval/resume execution structurally and in actual serialized size, while preserving effects. It does not achieve the declared temporal indistinguishability: aggregate timing AUC is 0.588 and combined AUC is 0.598. Therefore the final method cannot be frozen and paper writing should not begin.

## Evaluated method

M3 combines the existing Path-ORAM access abstraction, H=5 bounded normalization, fixed 16,384-byte frames, P99-derived live cadence, a public approval epoch, and an effect-safe public commit slot. PIR was removed because no independent registry observer exists. Full-cover dispatch is supporting only.

## Public runtimes and workload

The unmodified native security semantics were Microsoft Agent Framework `ToolApprovalMiddleware` and OpenAI Agents SDK HITL/RunState resume. Forty public-derived tasks came from pinned tau2-bench and AgentDojo repositories. Each task was paired over authorization and provenance-history state while keeping the public task and effect fixed. Approval is native upstream behavior; provenance reconstruction is pre-existing mediator behavior, not a second upstream-native middleware family.

## Live execution

Native SDK work runs inside the live slots. Frames are materialized as actual target-length byte strings. Deadlines use `perf_counter`; timestamps are recorded after the real barrier and are not rewritten. Cadence parameters were selected from 64 pooled training episodes spanning both state families. P90/P95/P99 and 1 s/2 s approval windows were exercised.

## Privacy results

| View | Aggregate M3 AUC | Chance |
| --- | ---: | ---: |
| Structural | 0.518 | 0.500 |
| Size | 0.500 | 0.500 |
| Timing | 0.588 | 0.500 |
| All features | 0.598 | 0.500 |

M0 and M1 were essentially perfect classifiers. M2 suppressed structural leakage but size and/or timing remained. M3 fixed size exactly and retained a measurable live timing channel. Detailed runtime/family values and shuffled controls are in `results_stage12/variant_summary.csv`.

The aggregate shuffled-label AUC was 0.5004; the M3 shuffled baseline was 0.5010.

Public bucketing reduced bytes but did not preserve the leakage class because real native response sizes crossed bucket boundaries. Fixed size remains the only passing size mode.

## Function and effect safety

All protected runs preserved authorization, public effect type/arguments, sanitized output, and persistent history outcome. Each successful execution committed exactly one real effect. Dummy external effects were zero. The full regression suite passed: 108 tests.

## Horizon and failures

H=3 covered only 50% and overflow perfectly revealed the absent state. H=5 and H=8 covered all logical paths; H=5 was selected because H=8 raised dummy fraction from 0.25 to 0.531. Exceptions and approval/service timeouts abort before commit in the tested core. Rare retry/recovery timing is not yet fully normalized.

## Utility and non-regression boundary

Twenty tau2 reference-action replays retained 100% action/final-ledger correctness. Twenty AgentDojo reference-action replays retained the same benign effects and authorization decisions. These are mechanism-isolation replays, not live model benchmark scores. ToolPrivacyBench could not run because its pinned official repository contains no released code or data. Thus public utility/security evidence is partial.

## Supporting costs

Path-ORAM mean simulated access latency rose from 25.3 us at 256 records to 82.0 us at 16,384 records; bytes/access rose from 36,864 to 61,440. Full-cover at N=4/8/16 reached the 1/N selected-agent baseline with 1.52x/2.73x/5.05x wall latency, 1.74x/6.12x/12.00x compute proxy, and N-fold bandwidth.

## Final judgment

The narrow research question remains meaningful, but the candidate M3 implementation is not ready to freeze. No new synthetic privacy discovery, ORAM, or PIR work is needed. The blocker is live temporal enforcement: a stronger scheduler/transport boundary must prevent or safely handle private-dependent overruns before the full structural-and-temporal claim can be supported.
