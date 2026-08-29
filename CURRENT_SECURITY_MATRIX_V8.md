# Current Security Matrix — V8

| Property | Status | Evidence / boundary |
|---|---|---|
| V7 freeze integrity | PASS | 460 frozen files; 225,936,117 bytes; V6 and pre-OHTTP V7 manifests included unchanged |
| OHTTP source gate | BLOCKED_NO_LOCAL_SOURCE | No permitted local RFC 9458/RFC 9292 source |
| OHTTP library audit | NOT_RUN | No candidate source to audit |
| RFC 9458 implementation | BLOCKED | No custom substitute |
| RFC 9458 Appendix A | NOT_TESTED | Prerequisite absent |
| RFC 9292 BHTTP | BLOCKED | No ad-hoc codec relabeling |
| PIR to authenticated V7 descriptor | PASS | 15/15 queries across 1K/10K/100K; fixed 1024-byte authenticated rows |
| PIR 100K V7 descriptor | PASS | 100,000 logical rows; 100,001 physical capacity; official pinned SimplePIR |
| Agent-service effect semantics | PASS | READ_ONLY, IDEMPOTENT_EFFECT, NON_IDEMPOTENT_EFFECT preserved and tested |
| Placement enforcement | PASS | STRICT fails closed; other profiles require explicit deployment policy/leakage |
| HTTP Relay metadata minimization | PARTIAL | Fresh-request allowlist implementation; Go compile/vet pass; runtime test blocked by Application Control |
| Trusted delivery ledger | PARTIAL | Durable state machine and Python tests pass; framework-callback ambiguity documented; canonical path unwired |
| Recovery live wiring | PARTIAL | Legacy queue is live; intended V8 state machines are unit/compile evidence only |
| Pacer critical path | PARTIAL | Minimal immutable-send path implemented; not live canonical and not timing tested |
| Admission/schedule binding | FAIL | Mechanical checks and tests implemented; V8 Go runtime test not completed under Application Control |
| Canonical OHTTP functional | BLOCKED | 0/0 admitted/delivered because prerequisites stopped execution |
| Canonical semantic fidelity | NOT_RUN | Holdout not frozen after blocked functional gate |
| Final request size invariant | OPEN | No real encapsulation size |
| Final response size invariant | OPEN | No real encapsulation size |
| Public round invariant | OPEN | No canonical run |
| STRICT structural privacy | OPEN | Fresh holdout correctly not run |
| STRICT size privacy | OPEN | Fresh holdout correctly not run |
| Timing privacy | OPEN / NOT_TESTED | Explicitly outside this closure |
| Packet-level timing | OPEN | No claim |
| Hardware TEE | NOT_TESTED | Local trusted abstraction only |
| Dummy provider operations | 0 | Canonical functional experiment did not run; this is an observed count, not efficacy evidence |

The main unresolved external dependency is an audited local RFC 9458 implementation with RFC 9292 support. Runtime validation of the new Go relay/admission/pacer tests is a separate host-policy limitation.

