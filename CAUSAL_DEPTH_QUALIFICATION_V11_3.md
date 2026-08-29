# V11.3 strictly causal qualification

All 1,000 sessions are fresh non-holdout development runs on the authorized Linux host. Each future action was generated only after the previous framework-visible result. The predeclared smallest-passing selection rule found no admissible candidate.

| A | Horizon | R | Lifetime | 10 actions | 20 actions | 30 actions | 50 actions | Selected |
| -: | -: | -: | -: | -: | -: | -: | -: | :-: |
| 75 | 375 ms | 136 | 680 ms | 100/100 | 0/50 | 0/30 | 0/20 | No |
| 100 | 500 ms | 161 | 805 ms | 100/100 | 2/50 | 0/30 | 0/20 | No |
| 150 | 750 ms | 211 | 1055 ms | 99/100 | 50/50 | 0/30 | 0/20 | No |
| 200 | 1000 ms | 261 | 1305 ms | 100/100 | 50/50 | 30/30 | 0/20 | No |
| 300 | 1500 ms | 361 | 1805 ms | 100/100 | 50/50 | 30/30 | 0/20 | No |

The maximum candidate `A=300` passed 100/100 ten-action, 50/50 twenty-action, and 30/30 thirty-action sessions, but 0/20 fifty-action sessions. Across those fifty-action runs, 100 resolved actions were explicitly not admitted; one run also had one scheduler miss. No candidate therefore satisfies the all-session gate.

Observed failures were preserved as framework trajectories with fewer outcomes than requested, with underlying raw runner records retaining `resolved_not_admitted_ids` and schedule status. No failed session was retried.
