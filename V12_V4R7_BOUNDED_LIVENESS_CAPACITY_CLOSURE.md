# V12 V4R7 Bounded Liveness and Capacity Closure

The historical V4R7 functional result remains `FAIL`. The corrected contract separates `M=50` operation capacity from arbitrary sequential causal-depth progress within `H=4500 ms`; guaranteed causal depth 50 is `NOT_CLAIMED`.

The immutable historical failure reconciles as 39 admitted and correctly returned operations, 11 explicit post-window `PROFILE_ADMISSION_CLOSED` outcomes, and zero silent losses. The old unconditional exact-50 oracle is `OVERSTATED_BOUNDED_LIVENESS_CONTRACT`.

Fresh execution used 16/16 pre-frozen identities exactly once. Both OpenAI and Microsoft `CAPACITY_50` admitted and returned 50/50 operations with 50/50 `PROVIDER_OK`, zero rejected operations, zero silent loss, `R=521`, and `Q=100`. Both `CACHE_REUSE_30` units passed; in particular Microsoft confirms closure of the earlier 50 ms provider-timeout defect.

The bounded causal stress observed OpenAI 50/50 and Microsoft 50/50 admitted within this realization of H, with 0 and 0 explicit post-window operations respectively. These are descriptive observations, not guaranteed limits.

`FULL_FIXED_H_FUNCTIONAL_CORRECTNESS = PASS`; `OPERATION_CAPACITY_M50 = PASS`; `READY_FOR_DEVELOPMENT_DUPLEX_REPAIR_SMOKE = YES`. No reliability rerun, classifier, AUC, P20, or P25 execution occurred.
