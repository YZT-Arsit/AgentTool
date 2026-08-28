# Final method audit — historical, invocation method superseded

Private-dispatch and ORAM-backed invocation conclusions below are not active.

## Gate result

`C — TIMING/SIZE LIVE DEFENSE FAILS`

The category label includes size, but the observed failure is timing. Actual fixed-size framing succeeds.

## P0 inventory

| Item | Evidence | Status |
| --- | --- | --- |
| Two independent public L2 runtimes | Native Agent Framework and OpenAI SDK approval/resume | pass |
| 30--50 public-derived tasks | 40 pinned tasks | pass |
| Two state families | Native approval plus mediator provenance-history | pass with external-validity qualification |
| Common IR/normalizer | one shared live core, zero task schedules | pass |
| Live size enforcement | actual 16 KiB binary frames | pass |
| Live cadence enforcement | actual barriers, no timestamp rewrite | implemented, privacy fail |
| tau utility | 20 deterministic reference-action replays | partial |
| ToolPrivacyBench | upstream artifacts unavailable | not run |
| AgentDojo security | deterministic action non-regression only | partial/not a live attack run |
| No dummy external effects | zero across runs | pass |
| ORAM scaling | 2^8--2^14 | pass |
| Small-N full-cover | N=4,8,16 concurrent harness | pass |

## Method maturity

`CONTROLLED PROTOTYPE`

It is no longer a trace-only toy: real native middleware, real serialized frames, and real wall barriers are exercised. It is not a general/system-level prototype because the timing claim fails and public benchmark executions are reference-action replays rather than full model-agent evaluations.

PIR is removed. Private dispatch remains supporting. No new ORAM or PIR mechanism is warranted. The next work is a scheduler/transport engineering correction with deadline admission, overrun handling that does not reveal private work, and measurement on a runtime with stronger real-time guarantees. This is not another synthetic leakage-discovery stage.
