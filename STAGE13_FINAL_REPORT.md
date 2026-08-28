# Stage 13 final report

## Executive decision

**C — STRUCTURAL/SIZE PROFILE VALID, TIMING PROFILE FAILS**

Stage 13 validates implementation feasibility of a finite paced-cover transport prototype, not a full agent-trajectory privacy system. Exact count/order/size invariants hold and pooled arrival classifiers are near chance, but state-family timing attacks remain significant. One Microsoft M3 episode out of 192 failed closed, so the bounded integration also does not preserve effects perfectly.

## Revised scope and threat model

The Privacy Kernel is trusted. The LLM, specialist workers, execution server, and RPC/transport host form one honest-but-curious compute plane. Protocol-visible activation, message size, and communication timing are protected targets. Microarchitecture, caches, GPU/performance counters, global Internet traffic analysis, and arbitrary human latency are excluded.

The current channel is persistent and outbound only. The five-slot epoch tests the transport primitive; it does not model the complete adaptive trajectory or the eventual bidirectional request/response channels.

## Implementation and first divergence

T0–T9 instrumentation localized the original Stage-12 leak. Application-level cadence was above the socket boundary, and a same-process receiver was starved by the Python GIL. A dedicated sender plus separate receiver process repaired post-epoch arrival bunching. A sender-owned acknowledged epoch start fixed reset/start races, and a fixed guard makes late proposals fail closed.

Residual divergence first appears around T4–T7. State-conditioned deadline slips and send/receive processing remain distinguishable in several natural state families.

## Evidence

| Result | Value |
|---|---:|
| Cross-runtime pooled structural LR | 0.518 (CI 0.479–0.570, p=0.176) |
| Receiver-visible size | 0.500 exactly |
| Microsoft strongest timing attack | 0.795 (authorization commit, within-task LR) |
| OpenAI strongest grouped timing attack | 0.710 (authorization send-to-receive LR) |
| OpenAI pooled send-to-receive LR | 0.571 (p=0.039) |
| Cross-runtime pooled receiver-arrival LR | 0.515 (CI 0.488–0.538, p=0.275) |
| Dummy external effects | 0 |
| Microsoft M3 overflow | 1/192 (0.52%), fail closed |
| OpenAI M3 overflow | 0/192 |
| Regression suite | 115 passed |

The acceptance rule required every attack to have AUC at most 0.55, a CI overlapping 0.50, and no significant permutation evidence. It is not met.

## Cadence and overhead

P99+1ms selected 4.2921 ms for Microsoft and 6.2975 ms for OpenAI. M3 mean latency was 21.57 ms and 31.66 ms, respectively, about 2.11x and 2.35x M2. Dummy fractions were about 50%. Deadline-miss rates were 1.25% and 1.46% in the repeated measured phase.

## Correctness

All cover envelopes caused zero external effects. The commit gate now satisfies `effect_count == admitted_at_guard`. However, one legitimate Microsoft proposal missed the guard and failed closed, so authorization safety is preserved but full authorization/effect equivalence is not.

## Scientific validity boundary

Repeated engineering repairs used outcomes from the nominal frozen split. The unchanged 40-task workload is therefore development evidence only. No result in this report is an untouched confirmation. A fresh holdout is mandatory before a timing-privacy claim.

## Benchmarks

Live tau2 and AgentDojo runs were not performed because timing did not clear the gate and the scope narrowed to the transport primitive. ToolPrivacyBench remains an official placeholder without executable artifacts.

## Conclusion

Profile S (address/count/order/size) remains defensible for the evaluated abstraction. Profile H is not validated. The next step is not a new privacy task, ORAM, or PIR construction; it is a bidirectional persistent paced-cover channel, frozen failure semantics, and one fresh untouched confirmatory holdout.
