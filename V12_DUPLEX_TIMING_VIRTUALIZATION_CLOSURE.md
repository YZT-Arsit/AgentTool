# V12 duplex public timing virtualization closure

Base attribution evidence: `d22519ca1d8cce0c7fba5a9c3fa950a11bc8824b`. The decisive P10 result remains `EARLY_TIMING_DISTINGUISHABILITY` with 6/10 early failures. This phase produced no protected timing sessions, classifier fits, AUCs, sentinel, confirmation, or holdout.

The implementation now has three independently public clocks: the preserved forward action clock, a trusted Gateway response commitment/release clock, and an open-loop Registry PIR query clock. The strengthened Relay application observer records both sides of both Relay interfaces. Registry answers also use a fixed public 50 ms release delay. Fixed public dimensions remain request 1079 bytes, response 800 bytes, Q=100, and R=506/279/233 for Delta10/20/25.

The deterministic security gates passed: T7-like and T9-like response deadlines are invariant to private readiness/action semantics; Registry query deadlines are invariant to real-resolution count; commitment and release paths remain separate; and the Go race gate passed. Pre-execution integrity bound 108 source files, 9 imported module probes, and 2 binaries to implementation commit `076bdbe18ffdd982462cd502b30f7b14a46eb520`.

Functional closure did not pass. The fresh frozen campaign completed P10 at 16/16, then reached 15/16 in P20. The Microsoft `CACHE_REUSE_30` unit returned only the first 13 of 30 expected operation IDs and failed at framework operation-ID reconciliation. The exact trigger was not established in this phase. In accordance with the frozen no-retry/no-replacement policy, the campaign stopped after 32/48 identities; P25 and all protected timing campaigns were not run. All 48 identities are development exclusions.

## Required report

```text
BASE_ATTRIBUTION_EVIDENCE: d22519ca1d8cce0c7fba5a9c3fa950a11bc8824b
REDESIGN: DUPLEX_PUBLIC_TIMING_VIRTUALIZATION
GATEWAY_RESPONSE_CLOCK: IMPLEMENTED
GATEWAY_RESPONSE_COMMITMENT: IMPLEMENTED
RELAY_RESPONSE_INDEPENDENT_OF_GATEWAY_SECRET_WORK: YES_MECHANICALLY
STRENGTHENED_RELAY_OBSERVER: client_to_relay_receive_ns, relay_to_gateway_send_ns, gateway_to_relay_receive_ns, relay_to_client_send_ns, session, public_slot, fixed sizes, public profile
REGISTRY_OPEN_LOOP_QUERY_CLOCK: IMPLEMENTED
REGISTRY_QUERY_SEND_INDEPENDENT_OF_PRIOR_PRIVATE_COMPLETION: YES_MECHANICALLY
REGISTRY_RESPONSE_SHAPING: IMPLEMENTED
FIXED_REQUEST_BYTES: 1079
FIXED_RESPONSE_BYTES: 800
FIXED_RELAY_CELL_COUNT: Delta10=506, Delta20=279, Delta25=233
FIXED_REGISTRY_QUERY_COUNT: 100
SYNTHETIC_T7_RESPONSE_DIFFERENTIAL: PASS
SYNTHETIC_T9_RESPONSE_DIFFERENTIAL: PASS
SYNTHETIC_REGISTRY_REAL_COUNT_DIFFERENTIAL: PASS
FUNCTIONAL_OPENAI: 16/16 executed PASS
FUNCTIONAL_MICROSOFT: 15/16 executed PASS; P20 CACHE_REUSE_30 failed after 13/30 returned operations
POST_CHANGE_TESTS: local Python 29 passed/1 skipped; remote Python 29 passed/1 skipped; canonicalv9 PASS; v9ohttp PASS; canonicalv9 race PASS; SimplePIR bridge PASS; named deterministic differentials 4/4 PASS
TRANSITIVE_RUNTIME_INTEGRITY: PASS (108/108 files, 9/9 module probes, 2/2 binaries)
NEW_PROTECTED_TIMING_SESSIONS: 0
P20_SENTINEL: NOT_RUN
P25_SENTINEL: NOT_RUN
TIMING_PRIVACY: INCONCLUSIVE
TIMING_GO: NO
READY_FOR_FRESH_DUPLEX_SENTINEL: NO (functional gate failed)
```
