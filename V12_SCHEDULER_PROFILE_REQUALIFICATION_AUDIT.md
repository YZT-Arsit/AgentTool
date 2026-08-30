# V12 scheduler profile requalification audit

The candidate set was frozen before execution as 10, 20, and 25 ms. No candidate was added after observing an outcome.

| Period | Schedule-only | Workload | Verdict |
|---:|---:|---:|---|
| 10 ms | 93/1000 before first miss | Not run | FAIL |
| 20 ms | 954/1000 before first genuine miss | Not run | FAIL |
| 25 ms | 1000/1000 | 135/240 before first miss | FAIL |

The first 20 ms attempt stopped at a diagnostic isolation false negative even though its session was complete and had no miss. That output is preserved. The same identity was not retried; a wholly new identity manifest was frozen before the decisive 20 ms campaign.

No candidate satisfied the complete schedule-only plus workload reliability criterion. Consequently there is no selected replacement public period. The existing 10 ms profile also remains failed for final qualification. Per the predeclared protocol, normal development qualification stopped and no V12 candidate universe, seed, selected manifest, execution plan, authorization, or confirmatory result was created.

