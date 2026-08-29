# Development Pair Precheck V9.1

These are development-only sanity checks, not holdouts and not paper confirmation.

| Category | Arms | Functional | Structural exact | Size exact | Result |
|---|---:|---:|---:|---:|---:|
| PUBLIC_CAPACITY_SWEEP | 5 | False | True | True | False |
| DIFFERENT_AGENT | 2 | True | True | True | True |
| DIFFERENT_TOOL | 2 | False | True | True | False |
| DIFFERENT_ACTUAL_COUNT | 2 | False | True | True | False |
| REPEATED_VS_VARIED_TARGET | 2 | False | True | True | False |
| DIFFERENT_COMPLETION_BEHAVIOR | 2 | False | True | True | False |

All 15 arms used `V9_1-STRICT-H50-P1`, one session, 111 Relay rounds, and the same scheduled lifetime. All functional gates include real PIR descriptor selection, authorization/routing, provider invocation, result delivery, no missing/unexpected result, no duplicate provider call, zero dummy provider work, and zero overflow.

Timestamps were not classified or compared for privacy.
