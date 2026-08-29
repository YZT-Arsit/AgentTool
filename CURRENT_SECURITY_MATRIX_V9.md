# Current Security Matrix — V9

| Property | Status | Evidence |
|---|---|---|
| V8 freeze integrity | PASS | Commit `335ccbcb...`, tree `9401f4d...`, 74 frozen evidence entries |
| OHTTP source provenance | SOURCE_TREE_HASH_ONLY | 228-file manifest; source tree SHA-256 `264221b5...`; no completed Git object verification |
| Offline vendor build | PASS | Go 1.26.5, proxy disabled, supplied vendor tree |
| Upstream OHTTP/BHTTP tests | PASS with 1 vector skip | 18 pass; `TestVectorVerify` skipped because vectors absent |
| RFC 9458 implementation | PASS | Round trip plus malformed/context tests |
| RFC 9458 Appendix A | BLOCKED_VECTOR_NOT_SUPPLIED | No official vector locally supplied |
| RFC 9292 BHTTP | PASS | All required private request/response cases |
| PIR-to-V7 descriptor regression | PASS | V8 11/11 plus post-OHTTP SimplePIR smoke 4/4 |
| Agent effect-semantics regression | PASS | V8 regression |
| Placement-enforcement regression | PASS | V8 regression, including STRICT fail closed |
| Real OHTTP Relay | PASS | Two loopback rounds, byte equality/header suppression/keep-alive |
| Trusted delivery ledger wiring | PARTIAL | Components pass; canonical wire path absent |
| Recovery live wiring | PARTIAL | Components retained; canonical command absent |
| Pacer final-send runtime | PARTIAL | Prepared fixed send passes; real canonical response not wired |
| Admission binding implementation/runtime | PASS / PASS | Linux positive and seven mismatch classes |
| Canonical OHTTP functional | BLOCKED, 0/0 | Full composition missing |
| Canonical semantic fidelity | NOT_RUN | Functional prerequisite not met |
| Development request/response sizes | PASS | 1079/800 exact across required cases |
| Final request/response size invariants | OPEN | Public profile not frozen |
| Public round invariant | OPEN | No canonical execution |
| STRICT structural/size privacy | OPEN | No fresh holdout |
| Timing privacy | OPEN / NOT_TESTED | No confirmation |
| Packet-level timing | OPEN | No claim |
| Hardware TEE | NOT_TESTED | Unchanged |
| Dummy provider operations | 0 | Canonical experiment not run |

