# Timing attack report

The complete machine-readable matrix is in `TIMING_ATTACK_RESULTS.csv` (528 rows). It includes LogisticRegression and RandomForest, grouped-task and repetition holdout splits, 50 grouped bootstrap samples, 50 within-task label permutations, confidence intervals, and p-values.

## Strongest reproducible residuals

| Runtime / family | Feature | Split/model | AUC | 95% CI | Permutation | p |
|---|---|---|---:|---:|---:|---:|
| Microsoft / authorization | commit time | within-task LR | 0.795 | 0.610–0.910 | 0.538 | 0.039 |
| OpenAI / authorization | send-to-receive | grouped-task LR | 0.710 | 0.611–0.789 | 0.504 | 0.020 |
| OpenAI / authorization | receiver processing | grouped-task RF | 0.697 | 0.564–0.791 | about 0.5 | 0.020 |
| Microsoft / provenance | release slip | grouped-task RF | 0.602 | 0.527–0.719 | about 0.5 | 0.039 |

## Pooled receiver view

Pooled grouped-task receiver-arrival AUCs were 0.525/0.444 for Microsoft (LR/RF) and 0.453/0.488 for OpenAI. These broad averages are near chance, but they do not satisfy the predeclared “no attack” rule because natural state-family attacks remain significant.

## Interpretation

The separate receiver process repaired the GIL-induced post-epoch burst. It did not validate high-assurance timing privacy. Multiple significant state-family attacks, state-dependent deadline-slip tails, and a 0.52% fail-closed overflow remain. Because repair decisions repeatedly inspected this corpus, all numbers are exploratory development evidence.
