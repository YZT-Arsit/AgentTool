# V13 two-tier private Agent resolution closure

This development revision adds the interface and structural integration for **Two-tier private Agent resolution** without changing the frozen V4R8 timing runtime, Gateway profile, PIR primitive, or observer definitions.

## Final status

| Field | Result |
|---|---|
| `BASE_RUNTIME` | `63319014f560f46e2a46dd140f53551e43c27e0d` |
| `DESIGN` | `TWO_TIER_PRIVATE_AGENT_RESOLUTION` |
| `PSI_COMPONENT` | Interface, fixed public profile, padding, Enterprise Agent Directory, fixed PSI/PIR orchestration, existing-PIR adapter, common-Gateway handoff, and deterministic mock backend implemented |
| `PSI_CRYPTO_BACKEND` | `NOT_CRYPTOGRAPHICALLY_INSTANTIATED` |
| `ENTERPRISE_DIRECTORY` | `IMPLEMENTED` as the split-domain logical directory model |
| `CANDIDATE_BATCH_K` | `8` |
| `ENTERPRISE_CARDINALITY_POLICY` | `PADDED` to public bound `1024` |
| `FIXED_PSI_SCHEDULE` | `PASS` -- exactly one slot per resolution |
| `FIXED_PIR_FALLBACK_SCHEDULE` | `PASS` -- exactly one existing scheduled PIR slot per resolution |
| `LOCAL_HIT_PIR_BEHAVIOR` | `PADDING_QUERY` to reserved dummy row |
| `LIBRARY_MISS_PIR_BEHAVIOR` | `REAL_QUERY` |
| `LOCAL_VS_LIBRARY_PUBLIC_STRUCTURE` | `INDISTINGUISHABLE_BY_CONSTRUCTION` at the structural adapter contract |
| `GATEWAY_COMMON_PATH` | `PASS` |
| `CORRECTNESS_TESTS` | V13 `21/21 PASS`; targeted regression `55 PASS`, `0 FAIL`, `1` platform skip |
| `NEW_SECURITY_ATTACK_EXPERIMENTS` | `0` |
| `PSI_MICROBENCHMARK` | `NOT_RUN` -- `NO_CRYPTOGRAPHIC_BACKEND` |
| `EXISTING_TIMING_RUNTIME_CHANGED` | `NO` |
| `EXISTING_GATEWAY_PROFILE_CHANGED` | `NO` |
| `PAPER_FILES_MODIFIED` | `NO` |

## Implemented flow

The trusted runtime accepts one to eight canonical `AgentDescriptorV7.agent_id` values. The fixed-profile availability resolver pads the candidate side to exactly eight identifiers. The modeled enterprise PSI side is padded to a public cardinality bound of 1024. A deterministic functional-only backend returns the intersection in tests; it exchanges raw identifiers and is explicitly prohibited from deployment.

Every successful resolution consumes one PSI slot and one PIR slot. An enterprise-local hit consumes the PIR slot with the existing reserved padding row. A miss consumes the same kind of public PIR opportunity with the required global Agent Library row. Both destinations enter the same `TrustedGatewayHandoff`. The public view contains only the public profile, slot counts, and unchanged V4R8 `R=521`/`Q=100` counts; it excludes candidate IDs, intersection, hit bit, selected route, PIR behavior, and execution handle.

Multiple enterprise matches use the frozen deterministic policy `FIRST_PLANNER_ORDER_MATCH_ELSE_FIRST_CANDIDATE`. A PSI error fails closed, but still consumes the fixed padding PIR slot; it never silently switches to the global library.

If the Enterprise Agent Directory resides wholly inside the same trusted runtime, the recorded deployment status is `PSI_NOT_REQUIRED_FOR_THIS_DEPLOYMENT_MODE`; ordinary private membership suffices. The PSI-facing design is for the split-domain directory deployment.

## Cryptographic boundary

No maintained PSI/OPRF/private-set-membership implementation was present in the repository or installed environment. Consequently this closure intentionally implements only the PSI interface, public profile, padding/scheduling contract, integration logic, and deterministic mock backend required for functional verification. It does not implement a hash exchange, Bloom filter, custom OPRF, or any other homegrown cryptography.

`INDISTINGUISHABLE_BY_CONSTRUCTION` is limited to the equal structural public shape at this adapter boundary. Cryptographic candidate/directory privacy requires a future vetted PSI backend conforming to the interface. Realized application-level timing indistinguishability is not claimed.

## Verification

The focused V13 matrix covers singleton hit, singleton miss, one/multiple matches, no hit, PSI error, enterprise and global common-Gateway routing, public branch equivalence, candidate sizes 1 through K, enterprise padding, and the adapter to the existing SimplePIR scheduler. The adjacent V4R8/duplex/PIR regression passed with one expected Windows platform skip.

The full historical repository suite was also sampled in this checkout: 460 passed, 14 skipped, and 62 failed because frozen Linux/Go binaries, archived result directories, and a Stage-9 environment are absent, plus pre-existing Windows-checkout historical hash mismatches. These failures are outside the V13 paths and were not repaired or reinterpreted. Exact commands and counts are preserved in `V13_TWO_TIER_PRIVATE_AGENT_RESOLUTION_TEST_RESULTS.json`.

No security attack campaign, classifier, AUC calculation, linking experiment, smoke sentinel, P20/P25, confirmatory run, or holdout was executed.
