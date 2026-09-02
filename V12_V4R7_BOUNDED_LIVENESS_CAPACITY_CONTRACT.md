# V12 V4R7 Bounded Liveness and Capacity Contract

`M=50` is the maximum number of real operations that may be admitted while a future public admission slot remains eligible inside the fixed `H=4500 ms` window. It is not a guarantee of arbitrary 50-step sequential causal progress.

The historical V4R7 functional result remains `FAIL`. Its immutable causal-depth trajectory reconciles exactly as 39 admitted and successfully returned operations, 11 explicit `PROFILE_ADMISSION_CLOSED` outcomes, and 0 silent losses. The old unconditional 50/50 oracle is classified as `OVERSTATED_BOUNDED_LIVENESS_CONTRACT` without rewriting that result.

The corrected development qualification separately tests `CAPACITY_50` with all intents made available in one framework turn and `CAUSAL_DEPTH_50_BOUNDED_HORIZON_STRESS` with explicit accounting of pre-window and post-window operations. Guaranteed causal depth 50 is `NOT_CLAIMED`.

No H, B, Delta, M, R, Q, duplex clock, observer contract, classifier, or AUC rule changes in this contract revision.
