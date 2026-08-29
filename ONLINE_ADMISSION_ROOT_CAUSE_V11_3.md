# V11.3 online admission root cause

The preserved V11.2 H50 profile used `M=50`, `A=50`, and `Delta=5 ms`, so its public admission horizon was only `A*Delta=250 ms`. That coupling came from the static/predeclared workload design. In an online causal trajectory, the maximum count of real operations and the number of public opportunities in which future operations may become ready are distinct public parameters. Three of 20 same-configuration V11.2 sessions therefore failed closed before the tenth action with `PROFILE_ADMISSION_CLOSED`.

Classification: `ONLINE_PROFILE_ADMISSION_HORIZON_TOO_SHORT`. This is not classified as scheduler, SimplePIR, OHTTP, or trajectory-privacy failure. The 17/20 result and all three failures remain immutable negative evidence.
