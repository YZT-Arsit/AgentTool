# Final Security Matrix

Statuses are scoped by the note; `PASS` never silently includes timing/resource privacy.

| # | Required item | Status | Evidence / boundary |
|---:|---|---|---|
| 1 | `REAL_PIR_CORRECTNESS` | PASS | Exact record recovery for all sampled indices |
| 2 | `REAL_PIR_100K_OPERATIONAL` | PASS | Physical 102.4 MB registry; 10/10 queries |
| 3 | `REAL_PIR_FULL_PREPROCESSING` | PASS | Real upstream `Setup`, 23.507 s at 100K |
| 4 | `END_TO_END_LOOKUP_PRIVACY` | PASS | SimplePIR query + common executor, structural/size scope; timing separately open |
| 5 | `COMMON_EXECUTOR_IDENTITY` | PASS | One `AgentControlExecutor` endpoint |
| 6 | `HANDOFF_PRIVACY` | PASS | H0-H3 contain no named physical Agent endpoint |
| 7 | `MULTIROUND_REPEATED_TARGET_UNLINKABILITY` | PASS | Raw-query AUC 0.490/0.494; structural/size scope |
| 8 | `MULTIROUND_FREQUENCY_PRIVACY` | PASS | No significant raw-query attack; timing attack remains open |
| 9 | `RARE_AGENT_PRIVACY` | PASS | No significant raw-query attack; timing remains open |
| 10 | `CROSS_SESSION_UNLINKABILITY` | PASS | 12 fresh processes; AUC 0.476/0.458 |
| 11 | `ACTION_TYPE_STRUCTURAL_PRIVACY` | PASS | Actual common RPC each slot; top-1 0.25 |
| 12 | `ACTION_TYPE_SIZE_PRIVACY` | PASS | Actual request/response sizes fixed at 1,024 bytes |
| 13 | `ACTION_TYPE_TIMING_PRIVACY` | OPEN | Top-1 up to 0.544; no timing shaper evaluated |
| 14 | `ACTION_TYPE_RESOURCE_PRIVACY` | OPEN | Resource top-1 up to 0.473; GPU not tested |
| 15 | `LOCAL_TOOL_PRIVACY` | PASS | Common Tool endpoint, structural/size scope |
| 16 | `REMOTE_TOOL_DESTINATION_PRIVACY` | PASS | Common egress boundary assumption required; post-egress observer excluded |
| 17 | `CLOUD_LOCAL_TOOL_PRIVACY` | PASS | Compute inside common Tool process; no named class worker |
| 18 | `TOOL_MULTIROUND_PRIVACY` | PASS | Structural/size only; timing attacks succeed |
| 19 | `HEAVY_EXECUTION_COST` | PASS | No dummy heavy operation; one real heavy operation per required real operation |
| 20 | `REGRESSION_CORRECTNESS` | PASS | Full suite reported in final report |

The aggregate system remains open, rather than fully secure, wherever a timing or resource observer is included.
The per-row structural/size passes support `CONDITIONAL_GO`, not `GO`.
