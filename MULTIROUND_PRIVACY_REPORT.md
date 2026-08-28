# Multi-round Privacy Report

## Scope and conclusion

Multi-round target privacy **passes for the cryptographic query plus structural/size view** and remains **open for
timing**. The result covers 16,000 real SimplePIR queries over 160 interleaved 100-round episodes. A separate test used
12 fresh bridge processes to test cross-session linking.

The final episode order was shuffled before execution. An earlier development run executed profile blocks in order
and created a temporal confound; it remains preserved under `results_crypto_closure/multiround/` but is not used as
final evidence.

## Workloads

The final run includes M0–M7: a single repeated Agent, a randomized rare Agent, balanced two-Agent sequences, at least
ten Agents, alternating A/B and A/C sequences, fresh session variants, and the same Agent across independent
sessions. Every round used fresh PIR query randomness, recovered the exact capsule, passed it into the common
executor, and emitted four fixed 1,024-byte control frames.

## Final attacks on raw server-visible queries

| Attack | Model | Score | Permutation | p | Result |
|---|---|---:|---:|---:|---|
| Same/different target AUC | Logistic regression | 0.490 | 0.500 | 0.714 | no advantage |
| Same/different target AUC | Random forest | 0.494 | 0.499 | 0.571 | no advantage |
| Frequency M0 vs M2 AUC | Logistic regression | 0.643 | 0.498 | 0.143 | not significant; small episode set |
| Frequency M0 vs M2 AUC | Random forest | 0.587 | 0.547 | 0.286 | not significant |
| Rare M0 vs M1 AUC | Logistic regression | 0.638 | 0.545 | 0.333 | not significant |
| Rare M0 vs M1 AUC | Random forest | 0.532 | 0.489 | 0.381 | not significant |
| A/B vs A/C AUC | Logistic regression | 0.425 | 0.506 | 0.714 | no advantage |
| A/B vs A/C AUC | Random forest | 0.419 | 0.517 | 0.762 | no advantage |
| 10-way Agent ID macro-F1 | Logistic regression | 0.093 | 0.099 | 0.619 | chance (0.1) |
| 10-way Agent ID macro-F1 | Random forest | 0.088 | 0.091 | 0.667 | chance (0.1) |

The frequency and rare tests contain only 40 episodes per pair. Their point estimates are therefore not treated as
proof of empirical equality; lack of stable target fields, exact structural/size equality, fresh queries, and the PIR
security argument carry more weight than these low-powered classifiers.

## Cross-session result

Across 12 independent process starts and 1,320 same/different pairs, raw-query AUC was 0.476 (logistic regression,
permutation p=0.952) and 0.458 (random forest, p=1.0). Structural/size views were exactly equal. No stable anonymous
pseudonym was found.

## Timing falsification

Timing is not closed. Frequency recovery from timing reached AUC 0.738 with logistic regression (permutation
p=0.0476). Transition timing reached AUC 0.664 with random forest, although p=0.095 in this sample. This prevents an
end-to-end timing-privacy claim. No application sleep or rewritten timestamp is used to relabel this result.

## Handoff sequences

H0–H3 (`A-B-C`, `A-D-E`, `A-B-A-B`, and `A-C-A-C`) use the same
`AgentControlExecutor/PROTECTED_CONTROL_SLOT` host shape. The logical target sequence is recorded only in
`private_handoff_ground_truth.jsonl`; the host trace contains no named Agent endpoint, worker, process, or queue.
This is a structural control atop the prior real-framework HANDOFF compilation, not a second claim of framework
coverage.

See `MULTIROUND_ATTACK_RESULTS.csv` and `results_crypto_closure/multiround_final/` for complete results and raw logs.
