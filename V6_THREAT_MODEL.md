# V6 threat model

| Observer | Trust | Visible in scope | Claim |
|---|---|---|---|
| `O_registry` | untrusted | SimplePIR query/answer dimensions, preprocessing state, server work | selected row hidden under official SimplePIR assumptions; encrypted rows hide descriptors |
| `O_cloud_network` | honest-but-curious | common endpoint, connection lifetime, cell count/order/size, socket timing, public profile | STRICT targets endpoint/count/order/size/profile equality; fine timing remains open |
| `O_cloud_host` | potentially malicious | normal non-confidential process memory/resource activity | no hostile-host secrecy from `LocalTrustedBackend`; a future attested TEE/CVM is required |
| `O_trusted_module` | trusted | capability, Agent ID, PIR client state, descriptor plaintext, route handle, keys | not an adversary |
| `O_gateway` | trusted external party | route handle and selected provider action | not an adversary in the base model |
| `O_provider` | destination party | its own invocation and arguments/results needed to serve it | necessarily learns its own invocation |

The payload-protection pipeline before `ProtectedActionIntent` is an explicit
prerequisite, not a V6 contribution. A cloud-local Tool with a distinct visible
process is not hidden from `O_cloud_host`. Denial of service, global traffic
analysis, microarchitectural/cache/GPU side channels, malicious firmware, TEE
implementation bugs, and packet-level timing are excluded.

`HARDWARE_TEE_ATTESTATION = NOT_TESTED`; `HARDWARE_MEMORY_CONFIDENTIALITY =
NOT_TESTED`; `ROLLBACK_PROTECTION = OPEN`.
