# Current Security Matrix

Snapshot: Linux functional continuation after IR-v2 core repair and canonical
single-Tool E2E execution. `PASS` is limited to the stated observer and tested
stratum.

| Property | O_registry | O_agentcloud | O_provider | Current status |
| --- | --- | --- | --- | --- |
| Registry index | protected by pinned official SimplePIR | not delivered | not delivered | PASS for cryptographic lookup; full E2E exercised at N=1,000, scale separately at N=100K |
| Logical Agent/capsule plaintext | client-only | forbidden by schema and absent from live trace | not delivered | PASS for live validated path |
| Logical HANDOFF target | private lookup/control state | absent from public trace; common endpoint retained | not delivered | PASS with preloaded-capsule limitation |
| Opcode/action/Tool identity | not applicable | encrypted fixed frame; absent from searched trace fields | provider necessarily sees its own action | structural/size PASS on evaluated seven-workflow subset; classifier sanity checks found no signal in the declared features |
| Slot count/order/width | public PIR profile | fixed public profile | outside base view | exact equality PASS on evaluated seven-workflow subset |
| Payload confidentiality/integrity | PIR construction | AES-GCM with authenticated version/direction/profile/session/slot | provider sees own plaintext | PASS for current framing |
| Replay/ordering | query freshness | duplicate, replay, wrong profile/direction, and non-monotonic frames rejected | outside base view | unit PASS |
| Model–Tool–Model semantics | not applicable | placement-independent | exact local provider result | PASS on 18/18 frozen Tool runs and live single-Tool E2E |
| Result reinsertion | not applicable | encrypted result envelope | local provider result | PASS on live validated path |
| Effect safety | not applicable | cover cannot request effect | operation ID/effect gate | normal completion and duplicate-ID tests PASS; timeout-after-effect ambiguity and durable restart idempotency OPEN |
| Dummy heavy operations | not applicable | fixed cover traffic only | no provider call for NOOP | 0 in completed Linux workflows |
| Timing | PIR answer timing separate/open | fixed-cadence mechanism exists | provider timing outside base view | NOT TESTED; host is not a timing reference platform |
| Resource metadata | server resources not claimed | coarse U resources in scope | provider resources excluded | OPEN |
| Packet-level TCP timing | not claimed | TCP socket-boundary only | not claimed | OPEN |
| Agent-as-Tool call/return | client-private call stack | common endpoint only in unit trace | child heavy primitive sees its own input | PARTIAL: compiler/runtime unit works; native framework call/return projection not executed |
| Real GPU model | not applicable | fixed encrypted frames | trusted local model provider sees model plaintext | PASS for one bounded Qwen2.5-0.5B-Instruct model -> Tool -> model case only |

The conjunction needed for a complete end-to-end privacy claim is not yet
established. In particular, long-horizon repeated/frequency/rare/transition
attacks, runtime PIR fetch on handoff, failure-path effect reconciliation,
corpus-wide IR-v2 support, timing, and resource privacy remain open.
