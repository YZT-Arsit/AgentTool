# V12 V4R7 Provider Completion Bound Closure

Root cause: `PROVIDER_COMPLETION_BOUND_TOO_TIGHT_FOR_DEPLOYMENT`.

The pre-outcome unprotected measurement completed 10000 trusted-Gateway provider attempts. End-to-end completion was p50 30.955893 ms, p90 59.937179 ms, p95 66.298969 ms, p99 74.090418 ms, p99.9 79.736184 ms, and max 83.676634 ms. Provider logical work was p50 0.183973 ms, p90 0.197691 ms, p95 0.20755 ms, p99 0.234851 ms, p99.9 0.38436 ms, and max 0.573281 ms.

The frozen rule produced `REQUIRED_BOUND_MS = 134` and selected `B = 200 ms`. V4R7 therefore has `completion_rounds = 20`, `R = 521`, and scheduled lifetime 5210 ms. Duplex response and Registry timing virtualization parameters are unchanged.

Fresh synthetic reliability: 200/200 PASS, retries 0, deadline misses 0, maximum release slip 4486398 ns.

Fresh P10 functional requalification stopped at the first genuine failure: 6 passed, 7 executed, 16 planned. OpenAI `CAUSAL_DEPTH_50` completed 39/50 framework operations; 11 later resolved actions were not admitted after the fixed H4500 admission horizon. Its 39 admitted provider calls were all `PROVIDER_OK`, and the 521-cell public transcript completed. Microsoft `CACHE_REUSE_30` was therefore not run. No identity was retried.

`READY_FOR_DUPLEX_REPAIR_SMOKE = NO`. `TIMING_PRIVACY = INCONCLUSIVE`; `TIMING_GO = NO`.
