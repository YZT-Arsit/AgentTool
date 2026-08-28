# Current Security Matrix

| Property | O_registry | O_agentcloud | O_provider | Current status |
| --- | --- | --- | --- | --- |
| Registry index | protected by SimplePIR | not delivered | not delivered | PASS |
| Logical Agent/capsule plaintext | client-only | forbidden by schema | not delivered | component PASS |
| Logical HANDOFF target | not in PIR server log | trusted state only | not delivered | evaluated subset PASS |
| Opcode/action/Tool identity | not applicable | padded ciphertext target | provider sees own action | OPEN end to end |
| Slot count/order/width | public PIR profile | fixed public profile target | outside base view | unit PASS; live OPEN |
| Payload confidentiality/integrity | PIR construction | AES-GCM with bound header | provider sees own plaintext | component PASS |
| Timing | PIR timing separate/open | isolated fixed cadence target | provider timing visible to itself | NOT TESTED for V3 |
| Resource metadata | server resources not claimed | U-only features in scope | provider resources excluded | OPEN |
| Effect safety | not applicable | cover cannot request effect | idempotency required | unit PASS; live OPEN |
| Tool semantic fidelity | not applicable | placement independent | must execute exact action | FAIL on evaluated ordinary Tool loop |
| Packet-level TCP timing | not claimed | open | not claimed | OPEN |

This matrix supersedes earlier `FINAL_SECURITY_DEFINITION*` documents for
current claims; those remain preserved historical artifacts.

