
# Final Pre-holdout Audit V9.1

V9 remains immutable at commit recorded in `V9_CANONICAL_FUNCTIONAL_FREEZE.json`.
V9.1 corrects only the privacy-use public-profile construction. One public H50
profile executed all development counts and paired workload variations with
exact structural and actual Relay-size equality and correct private semantics.

```text
V9_FUNCTIONAL_FREEZE: PASS
PUBLIC_PROFILE_INDEPENDENT_OF_ACTUAL_ACTION_COUNT: PASS
PUBLIC_PROFILE_ID_SECRET_FREE: PASS
PUBLIC_SESSION_COUNT_FIXED: PASS
PUBLIC_ROUND_COUNT_FIXED: PASS
PUBLIC_SCHEDULED_LIFETIME_FIXED: PASS
STRICT_STRUCTURAL_PROJECTION_DEFINED: PASS
STRICT_SIZE_PROJECTION_DEFINED: PASS
DEVELOPMENT_AGENT_PAIR: PASS
DEVELOPMENT_TOOL_PAIR: PASS
DEVELOPMENT_ACTION_COUNT_PAIR: PASS
DEVELOPMENT_REPETITION_PAIR: PASS
DEVELOPMENT_COMPLETION_PAIR: PASS
DEVELOPMENT_INTERNAL_EXTERNAL_PAIR: NOT_APPLICABLE
ALL_DEVELOPMENT_ARMS_FUNCTIONAL: PASS
DUMMY_PROVIDER_OPERATIONS: 0
DELIVERY_LEDGER: PARTIAL
TIMING_PRIVACY: OPEN / NOT_TESTED
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
READY_FOR_V10_HOLDOUT_FREEZE: YES
HOLDOUT_CREATED_OR_EXECUTED: NO
OVERALL_GO: NOT_ISSUED
```

No overall GO is issued. The next stage may freeze a fresh untouched V10
holdout; it must not reuse these development arms as confirmation.

## Preserved development failures and verification boundary

- `results_v9_1/development_precheck_failed_long_operation_ids/` preserves the
  first failed run: descriptive operation IDs exceeded the 32-byte wire ABI,
  collided after truncation, and were correctly deduplicated. Its results are
  not cited as the passing precheck.
- `results_v9_1/development_precheck_superseded_config_profile_projection/`
  preserves a functionally passing run whose structural projection read the
  configured profile ID rather than the actual Relay event. The final run fixes
  that audit gap and was rerun without changing the public profile.
- The V9.1 unit suite is 16/16 PASS and all 15 final raw Relay traces recompute
  to their saved projections. All 323 V9 freeze entries still match their
  recorded hashes.
- The Windows system Python was subsequently configured with the declared
  cryptographic, numerical, statistical, and two local framework dependencies.
  The complete suite reports `217 passed, 2 skipped`; both skips are explicit
  `NOT_COMPLETED_ENVIRONMENT` Pacer cases blocked by Windows Application
  Control. There are no test failures or errors. A fresh Go source rebuild was
  unavailable on the transferred Linux checkout because the vendored OHTTP
  source was absent. V9.1 changes no Go code and executed the already accepted,
  frozen canonical V9 binary; prior V9 regression evidence remains frozen.
