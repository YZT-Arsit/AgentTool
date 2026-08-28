# Long-horizon structural/size privacy report

## Frozen design

`LONG-HORIZON-STRUCTURAL-V1-20260828` was frozen and hashed before execution.
It defines eight leakage-equivalent families: Agent identity, handoff identity,
Tool class, frequency, rare target, transition pattern, repeated target, and
cross-session linkage. Each class contains 32 observation units and 128
canonical sessions. Aggregation windows are 1, 2, 4, 8, 16, and 32.

The required exact invariants are endpoint, direction/count/order, receiver-
visible frame size, slot/session indices, public profile, and persistent tunnel.
Timing is excluded from features and from any claim in this environment.

## Execution result

The first launch was blocked by Windows Application Control before any class
trace; that directory is preserved as
`results_long_horizon_structural_v1_attempt0_environment_blocked`. Because it
contained no privacy measurement, the unchanged frozen experiment was resumed
once after an unrelated public-header parsing repair.

All eight family pairs produced exactly equal endpoint/count/order/size/session
projections: 768 public events per case, 1,024-byte frames, one
`CommonActionGatewayV2` destination, and one tunnel. Grouped LogisticRegression
and RandomForest falsification checks were AUC 0.500 for aggregation windows
1/2/4/8/16/32. Dummy heavy operations remained zero.

## Mandatory functional-gate failure

These chance results **do not validate whole-workflow E2E privacy**. The frozen
3-slot, 10 ms profile was underprovisioned after durable journal fsyncs:

| Per class | Expected | Actual |
| --- | ---: | ---: |
| Completed observations | 32 | 0 |
| Real heavy operations | 96 | 32 |
| Delivered results | 96 | 0 |
| Workflow returned | Yes | No |

Only each observation's first model operation was emitted; the result arrived
after the three public slots and the kernel remained pending. Consequently the
valid narrow finding is transport-shape equality for emitted first-operation
prefixes. Agent/handoff/Tool/frequency/rare/transition/repetition/cross-session
whole-workflow privacy remains **OPEN**. `LONG_HORIZON_FUNCTIONAL_AUDIT.csv`
records every failed class.

The runner's pre-functional-check summary is retained as
`LONG_HORIZON_STRUCTURAL_SUMMARY_RAW_UNAUDITED.json`; the citable interpretation
is `LONG_HORIZON_AUDITED_SUMMARY.json`.

No cadence retuning or rerun is permitted for this frozen experiment. A future
development profile may be engineered separately, followed by another genuinely
fresh confirmatory definition.
