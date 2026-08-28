# Timing and Size Shaping Design

## 1. M3 mechanism

M3 composes the existing M2 bounded structural schedule with:

```text
H     public round horizon
Delta public round cadence
B     public message-size bucket/bound
W     public approval epoch/window
```

For successful executions in one leakage class, each host-visible slot has the same operation class, public destination class, padded request/response size, and scheduled offset. The final real effect occurs only at the public commit slot.

Implementation: [shaping.py](stage11_core_redesign/shaping.py).

## 2. Size shaping

Each internal request/response is padded to `ceil(length / B) * B`. The current controlled configuration uses `B=1024` bytes. Real and cover payloads are encrypted/authenticated under domain-separated message types and must have identical error behavior. Oversize values enter a declared larger public bucket or fail closed; truncating required authorization data is forbidden.

The Stage-9/10 B2 prototype already used equal serialized filler sizes, so its measured structural signature included equal size. Stage 11 promotes that behavior into the security definition instead of treating it as incidental.

## 3. Cadence shaping

The controlled scheduler exposes:

```text
t(round r) = W + r * Delta,  1 <= r <= H
```

The scheduler records contractual offsets rather than sleeping. A live runtime adapter must enforce them at the transport boundary and handle OS/network jitter using a declared public tolerance bucket.

Cadence candidates were derived from the preserved OpenAI Agents SDK Stage-10 continuation measurements:

| Configuration | Delta | H=5 mediation time | W=1000 ms total release |
|---|---:|---:|---:|
| P90 | 3.3557 ms | 16.7785 ms | 1016.7785 ms |
| P95 | 3.4347 ms | 17.1735 ms | 1017.1735 ms |
| P99 | 4.7097 ms | 23.5485 ms | 1023.5485 ms |

These are local Python percentiles, not production SLOs. See [cadence_tradeoff.csv](results_stage11/cadence_tradeoff.csv).

## 4. Human approval epoch

Both approval states enter the same public window `W`:

- **approval exists:** execute only internal protected cover mediation; do not prompt the user;
- **approval needed:** issue one real prompt through the trusted local UI;
- **both successful:** continue only at the public `W` boundary;
- **no decision by W:** fail closed before the effect under a public timeout outcome.

No dummy human prompt is generated. This removes approval-wait timing only at the cost of delaying the already-approved path by approximately `W` and imposing a deadline on the approval-needed path.

## 5. Controlled result

Across three seeds and 20 paired authorization executions per seed:

| Variant | Structural AUC | Size AUC | Timing AUC | Combined AUC |
|---|---:|---:|---:|---:|
| M0 natural | 1.000 | 1.000 | 1.000 | 1.000 |
| M1 per-action | 1.000 | 1.000 | 1.000 | 1.000 |
| M2 bounded structural | 0.500 | 0.500 | 1.000 | 1.000 |
| M3 bounded + size + cadence | 0.500 | 0.500 | 0.500 | 0.500 |

M3 non-physical trace sets are exactly equal in all seeds; every successful run has one real effect and zero dummy external effects. This is a deterministic controlled-scheduler check, not evidence that live network timing is normalized. Raw rows and 200-shuffle controls are in [shaping_per_seed.csv](results_stage11/shaping_per_seed.csv).

## 6. Overflow and throughput

For public `Delta`, any round that cannot finish before its release boundary must use a class-wide overflow rule. Options are a larger public cadence class or fail-closed overflow before effect. Silent deadline stretching would leak the private path.

Steady-state single-flow latency is at least `W + H*Delta`. Batching independent leakage classes at a public cadence can improve throughput but must not create secret-dependent batch occupancy. Production queueing and contention remain P0 measurements.

## 7. Implementation status

```text
Controlled trace scheduler: PASS
Size-bucket invariant tests: PASS
Approval-window fail-closed test: PASS
No dummy human prompts: PASS
No dummy external effects: PASS
Live Microsoft transport enforcement: NOT IMPLEMENTED
Live OpenAI transport enforcement: NOT IMPLEMENTED
```
