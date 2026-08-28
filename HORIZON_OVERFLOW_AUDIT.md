# Horizon and overflow audit

| H | Coverage | Overflow | Privacy AUC from overflow | Latency proxy | Dummy fraction |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 0.50 | 0.50 | 1.000 | 29 ms | 0.000 |
| 5 | 1.00 | 0.00 | 0.500 | 35 ms | 0.250 |
| 8 | 1.00 | 0.00 | 0.500 | 44 ms | 0.531 |

At H=3, both present-state classes fit and both absent-state classes overflow: conditional overflow is therefore perfectly secret-dependent. H=3 is rejected. H=5 covers all evaluated authorization and provenance paths; H=8 adds no coverage and substantially more dummy work. The selected horizon is H=5.

Internal errors, service timeouts, approval timeouts, and exceptions abort before public commit. Public failure may be treated as a separate leakage class; private retries must fit within H. Unit tests verify fail-closed behavior, but the timing of rare recovery paths is not comprehensively normalized.

