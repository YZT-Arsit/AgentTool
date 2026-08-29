# Current Security Matrix V7-OHTTP

| Property | Status | Evidence / limitation |
|---|---|---|
| REAL_SIMPLEPIR | PASS | Frozen official integration and 100K run |
| OHTTP_RFC9458_WIRE | NOT_IMPLEMENTED_OFFLINE | No compatible cached dependency |
| OHTTP_RFC_CONFORMANCE | NOT_TESTED | No RFC backend |
| AGENT_TOOL_ROUTE_SEPARATION | PASS | Python route tests |
| OPAQUE_CLOUD_RELAY | PARTIAL | Exact-copy/public-log contract tested; not actual OHTTP bytes |
| GATEWAY_RESULT_RELIABILITY | 161/161 pre-OHTTP | Queue/journal/admission gate |
| ACTION_MEDIATION_COVERAGE | 894/1370 = 65.26% | 473 partial, 3 unsupported; unchanged |
| FRESH_ACTION_SEMANTIC_FIDELITY | 24/24 pre-OHTTP | Adapter semantics only |
| STRICT_FUNCTIONAL_GATE | FAIL | Canonical OHTTP path not runnable |
| STRICT_STRUCTURAL_PRIVACY | OPEN | No actual OHTTP trace |
| STRICT_SIZE_PRIVACY | OPEN | Final HPKE lengths unmeasured |
| LONG_HORIZON_PRIVACY | OPEN | No OHTTP multi-slot run |
| TIMING_PRIVACY | NOT_TESTED | OHTTP does not close timing |
| PACKET_LEVEL_TIMING | OPEN | No lower-layer enforcement |
| HARDWARE_TEE_ATTESTATION | NOT_TESTED | Local trusted-process development only |
| DUMMY_HEAVY_OPS | 0 pre-OHTTP | No canonical OHTTP run |

The canonical strict gate is marked FAIL rather than inheriting the Legacy
transport PASS. This is an implementation-closure failure, not evidence that
RFC 9458 itself fails.

