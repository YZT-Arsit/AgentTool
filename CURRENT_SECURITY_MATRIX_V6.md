# Current V6 security matrix

| Property | Status | Evidence/boundary |
|---|---|---|
| Canonical IR dependency | PASS: NONE | import test and generic byte-row PIR wrapper |
| Local trusted module functionality | PASS | 8 V6 unit tests, 16-case holdout |
| Hardware TEE attestation | NOT_TESTED | local backend only |
| Host memory confidentiality | NOT_TESTED | local backend only |
| Rollback protection | OPEN | no non-rollbackable anchor |
| Real SimplePIR encrypted descriptor path | PASS | 1K/10K/100K full preprocessing |
| PIR 100K operational | PASS | 100,000 logical rows, 100,001 physical rows |
| Unified registry | PASS for selection component | mixed placement rows; live action composition partial |
| Hierarchical resolution | PASS functional / declared leakage | component Pareto model |
| Action mediation coverage | 894/1,370 fully mediated | 473 PARTIAL; 3 unsupported |
| Fresh action semantic fidelity | 16/16 | one-shot outbound-action holdout |
| Gateway protocol/recovery | PASS/PARTIAL | Go tests pass; restart and non-idempotent ambiguity open |
| STRICT structural privacy | OPEN | paired live run incomplete; only arm failed functional gate |
| STRICT size privacy | OPEN | same reason; unit format equality is insufficient |
| Long-horizon privacy | OPEN | no valid V6 dataset |
| Timing privacy | OPEN / NOT_TESTED | invalid reference platform; no new decision |
| Packet-level timing | OPEN | TCP socket boundary only |
| Resource privacy | OPEN | no hardware TEE/resource shaping |
| Dummy heavy operations | PASS: 0 | all completed V6 paths |
