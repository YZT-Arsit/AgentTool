# V12 causal-horizon requalification

The historical H3000 failure and all three prohibited identities remain preserved and were never retried. The nominal/effective commitment-clock mismatch was repaired with a public-dispatch-only effective slot state machine for both action and result commitment.

Deterministic replay admitted `50/50` under each frozen H candidate. PIR capacity and the joint causal model passed for H4500, H5000, and H6000 with the unchanged `K6 / PIR60 / EPOCH6000 / Q100` construction.

Post-change Linux gates passed: Python serial `75/75`, Python default `75/75`, native routing `15/15`, Go `79/79`, and security negatives `22/22`. Deployment integrity matched `696/696` files, `8/8` imported module paths, and `2/2` binaries.

The one-shot live campaign passed all `8/8` workloads at H4500, including depth50 on both pinned frameworks, K6 transitions, Agent-as-Tool transitions, and repeated cache-hit workloads. Therefore the frozen smallest-pass rule selects `H*=4500 ms`, `A=450`, `R=506`. H5000 and H6000 were not run.

This is functional causal-capacity qualification only. Timing privacy remains **INCONCLUSIVE**, timing GO remains **NO**, and packet-level timing remains **OPEN**. No timing attack, timing confirmatory session, final V12 universe, seed, holdout, authorization, or selected final V12 execution was created.
