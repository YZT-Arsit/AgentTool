
# Canonical Functional Report V9

| Bound | Delivered/admitted | Complete lifecycle | Relay events/rounds | Provider calls |
|---:|---:|---:|---:|---:|
| 1 | 1/1 | 1/1 | 13/13 | 1 |
| 10 | 10/10 | 10/10 | 64/64 | 10 |
| 50 | 50/50 | 50/50 | 144/144 | 50 |
| 100 | 100/100 | 100/100 | 244/244 | 100 |

Overall functional gate: **PASS**. Across 161 admitted actions: 161 provider calls, 161 framework results, zero missing/unexpected results, zero provider duplicates, zero dummy provider operations, zero profile overflow, and zero unexpected duplicate framework deliveries. The mixed workload covers TOOL and AGENT_SERVICE with read-only, idempotent, safe local non-idempotent, and local EXTERNAL_HTTP actions. Result completion was observably out of submission order in trusted logs, while public Relay records stayed fixed-width.

This is development/correctness data only. No AUC, indistinguishability result, or privacy claim is derived from it.
