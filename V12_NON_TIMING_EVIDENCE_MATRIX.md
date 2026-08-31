# V12 non-timing paper-evidence matrix

| Claim | Status | Boundary |
|---|---|---|
| PIR Agent selection | DEVELOPMENT_SUPPORTED | Real prebuilt query and preserved 100K evidence; not timing evidence |
| Descriptor authentication | CLOSED | Authenticated codec and tamper negatives |
| Private route resolution | LIMITATION | V12-RC identity/authorization tests pass; two Agent-IR Agent-as-Tool tests fail |
| Agent/Tool mediation | DEVELOPMENT_SUPPORTED | 894/1370 MEDIATED; 473 PARTIAL; 3 UNSUPPORTED |
| Framework semantic fidelity | LIMITATION | Level-A only; two frozen Agent-IR tests failed |
| Repeated Tool routing | DEVELOPMENT_SUPPORTED | Dedicated regressions pass, but broader Agent-as-Tool IR regressions fail |
| Provider diagnostics | CLOSED | Deterministic private classifier; historical error unresolved |
| Effect/recovery | CLOSED | Ambiguous non-idempotent outcome remains unknown, not exactly once |
| OHTTP/BHTTP path | CLOSED | Component correctness and negative tests |
| Structural/size projection implementation | DEVELOPMENT_SUPPORTED | Static/fixed-width implementation only; final timing profile unresolved |
| Corpus coverage | DEVELOPMENT_SUPPORTED | Frozen 894/473/3 classification |
| Timing privacy | DEFERRED_TIMING | OPEN / NOT TESTED |
| Packet-level timing | NOT_TESTED | OPEN |
| Hardware TEE | NOT_TESTED | Trusted software/local module plus trusted gateway, not an attested enclave |
| Source-body equivalence | LIMITATION | Executable subset 0; Level-A boundary only |

The matrix does not elevate the independently passing components above the failed aggregate Python gate.
