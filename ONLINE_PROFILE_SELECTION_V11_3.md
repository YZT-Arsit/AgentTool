# V11.3 online profile selection

The predeclared rule was applied exactly: evaluate A=75, 100, 150, 200, 300 in order and select the first candidate passing every required session. No candidate passed, so `selected_profile = null`. The task-authorized range was not extended after observing outcomes.

| A | Horizon | R | Lifetime | 10 actions | 20 actions | 30 actions | 50 actions | Selected |
| -: | -: | -: | -: | -: | -: | -: | -: | :-: |
| 75 | 375 ms | 136 | 680 ms | 100/100 | 0/50 | 0/30 | 0/20 | No |
| 100 | 500 ms | 161 | 805 ms | 100/100 | 2/50 | 0/30 | 0/20 | No |
| 150 | 750 ms | 211 | 1055 ms | 99/100 | 50/50 | 0/30 | 0/20 | No |
| 200 | 1000 ms | 261 | 1305 ms | 100/100 | 50/50 | 30/30 | 0/20 | No |
| 300 | 1500 ms | 361 | 1805 ms | 100/100 | 50/50 | 30/30 | 0/20 | No |

Post-selection qualification, final reliability, semantic regression, structural regression, invariants, and the deliberate finite-horizon negative test were not run because each requires an actually selected profile. This is a gate failure, not missing positive evidence to be inferred.
