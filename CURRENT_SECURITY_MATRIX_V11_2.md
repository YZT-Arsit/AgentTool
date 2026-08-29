# Current security matrix V11.2

| Property | Status |
| --- | --- |
| Online dynamic action ingress | PASS |
| Single public session per Agent run | PASS |
| Action n+1 after result n | PASS |
| Dynamic SimplePIR Agent resolution | PASS |
| Online Agent-as-Tool | PASS |
| OpenAI online handoff | PASS |
| Microsoft online handoff | NATIVE_MECHANISM_ABSENT |
| Internal/external mix | PASS |
| Structural/size regression | PASS |
| Semantic regression | PASS |
| Reliability stress | FAIL (Campaign D 380/380; same-config check 17/20) |
| Timing privacy | OPEN / NOT TESTED |
| Packet-level timing | OPEN |
| Hardware TEE | NOT_TESTED |
| Frozen mediation coverage | 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED |
| Source-body executable subset | 0, informational only |
