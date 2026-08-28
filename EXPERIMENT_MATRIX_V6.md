# V6 experiment matrix

This matrix records the requested gates. The semantic holdout had its own
pre-execution freeze. The PIR experiments follow the prompt-fixed scales and
metrics. The live Gateway privacy matrix below was **not** promoted to a frozen
confirmatory experiment: the first development arm failed functionality and
the environment blocked continuation.

| Secret | Observer | Mechanism/baseline | Workload | Metric and gate | Status |
|---|---|---|---|---|---|
| Agent row | registry | SimplePIR vs direct index | 1K/10K/100K repeated IDs | correctness, fresh queries, no private server fields | complete |
| descriptor plaintext | registry | row AEAD | mixed internal/external rows | tag/ID/epoch checks | complete |
| action semantics | framework boundary | native vs V6 mediation | 16 frozen cases | exact projection equality | complete once |
| endpoint identity | cloud network | direct/PIR-only/common Gateway | local providers | one public destination | partial live |
| identity/frequency/rare/transition | cloud network | V6 fixed transcript | eight paired 50-episode families | functional gate then exact shape/size equality | not completed |
| repeated/cross-session target | cloud network | V6 fixed transcript | windows 1/5/10/25/50 | exact equality then grouped classifier only if unequal | not completed |
| internal/external route | registry/network | unified vs hierarchical | hit-rate sweep | measured-component Pareto plus declared leakage | complete model |
| cache hit | registry/network | strict dummy query vs efficient skip | hit-rate sweep | work/bytes/leakage | complete model |
| fine timing | cloud network | Pacer | none on invalid host | no V6 confirmatory claim | open/not tested |
| resource class | cloud host | none | feature-domain audit | claim only if implemented | open |
