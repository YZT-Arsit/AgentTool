# Current security matrix V11

| Property | Status | Evidence boundary |
| --- | --- | --- |
| Native/canonical Level-A semantics | PASS | 38/38 non-holdout rows |
| RFC 9292/9458 fixed structure/size | PASS (development) | actual Relay projections |
| Internal/external STRICT structure/size | PASS (development) | one paired precheck |
| Dummy heavy work | PASS | 0 |
| Multi-action/session reliability | PARTIAL | 10/50 pass; one intermittent 1-action budget failure |
| Source-body semantics | NOT IMPLEMENTED | exact subset 0 |
| Timing privacy | OPEN / NOT TESTED | timestamps not classified |
| Packet-level timing | OPEN | not evaluated |
| Hardware TEE | NOT TESTED | local software backend only |
| Final holdout | NOT RUN | all V10/V10.1 outcomes remain unknown |
| Repository regression | PASS after environment cleanup | 268/270 initial; two binary-lock failures passed 2/2 after orphan test workers were stopped |
