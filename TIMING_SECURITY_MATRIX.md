# Timing Security Matrix

| # | Property | Status | Evidence / limitation |
|---:|---|---|---|
| 1 | `PIR_INDEX_PRIVACY` | PASS | Official SimplePIR, fresh queries, exact recovery |
| 2 | `PIR_FIXED_SCHEDULE_TIMING` | OPEN | Fixed real-query schedule works; combined pair AUC 0.527, p=0.035 |
| 3 | `MULTIROUND_STRUCTURAL_PRIVACY` | PASS | Count/order/size/common identities unchanged |
| 4 | `MULTIROUND_TIMING_PRIVACY` | OPEN | Several estimates remain wide or above the engineering gate |
| 5 | `CROSS_SESSION_TIMING_UNLINKABILITY` | PASS | AUC 0.438/0.359, non-significant |
| 6 | `RARE_AGENT_TIMING_PRIVACY` | PASS | AUC 0.278/0.306, CIs cover chance, non-significant |
| 7 | `AGENT_FREQUENCY_TIMING_PRIVACY` | PASS | AUC 0.361/0.319, CIs cover chance, non-significant |
| 8 | `HANDOFF_TIMING_PRIVACY` | OPEN | AUC 0.556/0.639, wide and non-significant but above gate |
| 9 | `ACTION_TYPE_TIMING_PRIVACY` | OPEN | No usable above-chance classifier, but results do not converge cleanly to 0.25 |
| 10 | `TOOL_CLASS_TIMING_PRIVACY` | OPEN | Top-1 0.250/0.458; RF remains above the 1/3 target |
| 11 | `TOOL_REPEATED_TARGET_TIMING_PRIVACY` | PASS | AUC 0.495/0.522, non-significant |
| 12 | `TOOL_FREQUENCY_TIMING_PRIVACY` | OPEN | AUC 0.639/0.667 with wide intervals |
| 13 | `TOOL_RARE_EVENT_TIMING_PRIVACY` | PASS | No transferable above-chance attacker; wide intervals noted |
| 14 | `TOOL_TRANSITION_TIMING_PRIVACY` | OPEN | LR AUC 0.708 with wide interval; insufficient closure evidence |
| 15 | `FIXED_EGRESS_DESTINATION` | PASS | One persistent `CommonActionGateway` TCP destination |
| 16 | `FIXED_FRAME_SIZE` | PASS | Exactly 1,024 bytes request and response per slot |
| 17 | `FIXED_FRAME_CADENCE` | PASS | Secret-independent deadlines; rare OS stalls remain ordinary noise |
| 18 | `RESULT_RELEASE_DECOUPLING` | PASS | Completion enters private queue; release only at public response slot |
| 19 | `DUMMY_HEAVY_OPS_ZERO` | PASS | NOOP never spawns provider work or effect |
| 20 | `RESOURCE_PRIVACY` | OPEN | Explicitly outside timing repair |

`PASS` means the stated experiment and boundary passed. It does not silently extend to packet-level timestamps,
resource privacy, colluding downstream providers, or arbitrary continuation-epoch leakage.
