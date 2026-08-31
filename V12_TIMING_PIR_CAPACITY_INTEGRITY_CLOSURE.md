# V12 timing PIR capacity/integrity closure

Final phase status: **FAIL — stopped at first fresh live-capacity failure**.

## What closed

- The prior timing campaign abort and `DEV-TD-CAPACITY50-P10-PIR60` are preserved; that identity was never retried.
- The stale remote runtime was replaced before new identities were frozen. Final preflight matched 696/696 transitive source artifacts, 10/10 actual Python import paths, and 2/2 Linux binaries.
- A no-secret, all-dummy preflight actually executed Q=100 queries and verified ordinal 0 at 25 ms, exact 60 ms nominal recurrence, dummy row 999, the prebuilt SimplePIR path, fresh query randomness, and the 50 ms fail-closed query bound.
- The old `Q=M` inference is rejected. The capacity candidate is fixed public epoch 6000 ms / period 60 ms / Q=100, with K=6 authenticated descriptor identities and trusted per-epoch descriptor reuse.
- The deterministic causal model and joint PIR/action proof pass. New descriptor arrivals are publicly bounded at 2589 ms; cached same-Agent actions do not consume additional real PIR queries.
- Post-change regression passed: Python serial 51/51, Python default 51/51, native routing 15/15, Go 70/70, and security negatives 22/22.

## Fresh live-capacity stop

The first frozen live workload, OpenAI same-Agent causal depth 50, passed every check. It executed 100 fixed PIR queries: 1 real, 99 dummy, with 49 trusted descriptor-cache hits; its session completed with the full fixed Relay transcript.

The second workload, `DEV-TPCIC-MS-SAME-AGENT-DEPTH50-001`, failed in the **native Microsoft framework before any canonical session or PIR query for that workload existed**. The native adapter expected 50 operation IDs but received exactly 40. The first missing ID was `op61c3152e355f792a53e35c3ad3fe`. The pinned framework source defines `DEFAULT_MAX_ITERATIONS = 40`, and the current adapter did not override that bound for this 50-step workflow.

The campaign stopped immediately. There was no retry, replacement, repair, execution of the remaining three workloads, timing attack session, timing confirmatory session, final timing-profile selection, candidate universe, seed, or selected V12 execution. The immutable raw root is `/root/autodl-tmp/results_v12_tpcic_live_capacity`.

This failure is not a PIR60 privacy result and does not invalidate the deterministic PIR capacity proof. It is nevertheless a live-capacity gate failure, so timing attack development may not resume until a separately labeled phase addresses and requalifies the current Microsoft native depth contract with fresh identities.

`TIMING_PRIVACY = INCONCLUSIVE`, `TIMING_GO = NO`, `PACKET_LEVEL_TIMING = OPEN`, and `HARDWARE_TEE = NOT_TESTED`.
