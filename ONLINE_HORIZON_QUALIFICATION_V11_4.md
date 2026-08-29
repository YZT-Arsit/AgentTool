# V11.4 online horizon qualification

Period selection occurred first and was frozen before these horizons were instantiated. Every row is non-holdout development evidence; failed sessions were not retried. Testing stopped after the first horizon satisfying all four causal-depth strata.

| Period | Passed | Sessions | Misses | Overflow | Dummy heavy | Silent loss | Selected |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 10 ms | 500/500 | 500 | 0 | 0 | 0 | 0 | Yes |

| H | A | R | Lifetime | Causal 10 | Causal 20 | Causal 30 | Causal 50 | Selected |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 2000 ms | 200 | 256 | 2560 ms | 100/100 | 50/50 | 30/30 | 0/30 | No |
| 3000 ms | 300 | 356 | 3560 ms | 100/100 | 50/50 | 30/30 | 30/30 | Yes |

Mixed-family qualification: 240/240 across 240 independently executed sessions.
