# Action-type Privacy Report

## Result

- Structural action-type privacy: **PASS** at the modeled protocol boundary.
- Serialized-size privacy: **PASS**.
- Timing privacy: **OPEN**.
- Resource privacy: **OPEN**.

The matched workload contains 800 randomized slots (200 each of `AGENT`, `LLM`, `TOOL`, and `NOOP`). Every slot
actually transmits one fresh 1,024-byte request and receives one 1,024-byte response from `CommonToolExecutor`.
Non-Tool actions use an internal NOOP that returns an acknowledgement without dispatching a Tool or invoking heavy
work. Thus the process/RPC activation modeled by the protocol is real rather than a rewritten metadata label.

| Features | Logistic top-1 | Random-forest top-1 | Chance | Finding |
|---|---:|---:|---:|---|
| Structural | 0.250 | 0.250 | 0.250 | exact public shape |
| Size | 0.250 | 0.250 | 0.250 | exact 1,024/1,024 bytes |
| Timing | 0.483 | 0.544 | 0.250 | distinguishable |
| Resource | 0.468 | 0.473 | 0.250 | distinguishable |
| All | 0.478 | 0.577 | 0.250 | distinguishable |

Random-forest timing macro-F1 was 0.541 and resource macro-F1 0.439, versus permutation top-1 near 0.25. LLM CPU
work remains particularly recognizable. The correct conclusion is not action-type privacy in general: fixed frames
close only the structural/size view.

GPU telemetry was unavailable and is `NOT_TESTED`. The experiment records client process CPU time, Python peak
allocation, RSS delta, and thread delta; it does not emulate hypervisor performance counters or confidential GPU
execution.

Observer records and labels are serialized separately in
`results_crypto_closure/tool_action/action_type_host_visible_trace.csv` and
`action_type_private_ground_truth.csv`. Complete classifier output is in `ACTION_TYPE_ATTACK_RESULTS.csv`.
