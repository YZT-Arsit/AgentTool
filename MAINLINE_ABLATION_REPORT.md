# Mainline Ablation Report

This ladder applies only to canonical V3. It does not merge historical Stage
metrics into a new privacy score.

| Transition | Intended removed leakage | Added cost / assumption | Measured conclusion |
| --- | --- | --- | --- |
| B0 -> B1 | Registry index from `O_registry` | SimplePIR preprocessing, query/answer bandwidth, trusted client state | Real 3-slot schedule passed correctness/freshness; named execution remains visible |
| B1 -> B2 | Named logical Agent activation in `O_agentcloud` | Trusted capsule/control placement and common executor | Logical HANDOFF unit path passes; ordinary Tool semantics fail |
| B2 -> B3 | Private opcode/progress through count/order/width | Fixed control/action horizons and cover frames | Exact frame/header/schema invariants pass in unit model; no live U trace |
| B3 -> B4 | Application-visible destination/size, nominally timing | Common Gateway and pacing | V1 is a valid `TIMING_NO_GO`, but its semantics do not match V3 and it is not aggregated |
| B4 -> B5 | Worker-contention timing at observer boundary | Separate Pacer/Worker, rings, fixed cutoff, persistent tunnel | Source/unit implementation exists; Windows policy prevented a live Pacer run |

`MAINLINE_ABLATION_RESULTS.csv` distinguishes component PASS, historical
failure, semantic FAIL, and environment incompletion. No B5 classifier was run:
without a complete live trace, doing so would test a simulator or partial path
rather than the declared observer.

Phase-6 conclusion: ablation construction is complete, but the complete V3 row
is **INCOMPLETE**. It cannot support structural, size, timing, or resource
privacy claims.

