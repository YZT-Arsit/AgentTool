# V12-RC routing stress audit

The one-shot development stress stopped permanently at workflow index 107. The
frozen identity manifest planned 280 workflows and has SHA-256
`2d591618a2c9c84dba9ed679ccf2793fc828cb1900ff24100d60447de9d52e86`.
The output root remains on the authorized Linux host at
`results_v12_rc_routing_stress`; it was not deleted, renamed, resumed, or
recycled.

Before the decisive stress, the generic Linux unit/integration suite passed
15/15. This covered sequential duplicate names with equal and unequal
arguments, ten repeated invocations, OpenAI parallel invocation, different
effect contracts under one logical name, Tool/Agent-as-Tool namespace sharing,
operation-ID rejection, and absence of the routing alias from canonical public
and private projections.

## One-shot outcome

- OpenAI two-action duplicate-name workflows: **100/100**.
- Microsoft two-action duplicate-name workflows: **0/100, not run** because an
  earlier decisive workflow failed.
- Long repeated-target workflows: **7/80 passed before failure**; the eighth
  attempted workflow failed and 72 were not run.
- Retry or campaign resume: **none**.

The failure was `DEV-RC-OA-REPEAT10-007`, a ten-action OpenAI trajectory. The
public session itself completed with 356 rounds, 10 admitted operations, 10
provider invocations, 10 delivered operation IDs, zero schedule misses, zero
profile overflow, zero silent committed-result loss, and zero dummy-heavy
operations. However, the first operation `opDEVRCOA1000700` returned canonical
private status `ERROR` with no payload despite the frozen `READ_ONLY/SUCCESS`
scenario. The other nine operations returned `RESULT`. This made the canonical
semantic projection differ from the native projection.

This is not another Tool-name collision: the operation-ID sets remained exact,
and `acv_private_route_` did not appear in the retained Go result. It is a
separate canonical provider-result reliability failure. The frozen Go engine
collapses HTTP transport errors, non-2xx responses, response-decode failures,
and provider status failures into one generic `ERROR` and does not retain the
underlying error string. Therefore the immutable evidence supports the exact
class `CANONICAL_PROVIDER_RESULT_ERROR_FIRST_OPERATION`, but not a narrower
subcause. A narrower claim would require a new diagnostic run, which this phase
forbids after the one-shot failure.

The postmortem JSON has SHA-256
`3c1f1f48e05438347948f0be66aee804da645ea160651d9943fdfed7bd6f02af`
and binds the failing Go result, private trajectory, control-event stream,
DeliveryLedger, effect-recovery journal, and ready-result journal.

Because the required long repeated-target gate is not 80/80, V12-RC stops here.
Class-A serial/default, Go, profile requalification, B4/B5 performance, privacy
matrix, security-negative regression, and all holdout-construction steps were
not run.
