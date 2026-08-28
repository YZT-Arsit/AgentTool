# Activation reintroduction audit V6

| Stage/field | Could identify target? | V6 disposition |
|---|---:|---|
| SimplePIR server query | no direct index/name in audited trace | PASS under PIR assumptions |
| encrypted descriptor row/hash | ciphertext is randomized; digest remains inside AEAD | PASS |
| trusted cache key | yes internally | TRUSTED_MODULE_ONLY |
| ActionCell ciphertext | no route/name plaintext in unit/E2E smoke | PASS |
| opaque cloud client arguments | no key or private workload in completed arm | PASS DEVELOPMENT |
| cloud endpoint | one `CommonActionGatewayV2` | PASS DEVELOPMENT |
| Gateway private provider config | concrete endpoint | TRUSTED_GATEWAY_ONLY |
| provider endpoint | identifies itself | PROVIDER_ONLY; unavoidable |
| CLOUD_LOCAL distinct process | identifies Tool to cloud host | FAIL for STRICT unless moved/brokered |
| experiment ground-truth files | contain labels | trusted test artifact, never attacker feature |

No V6 public trace may contain `/agent/<id>`, Agent-specific process/queue, route
handle, provider name, operation ID, or descriptor hash. The real PIR-to-frame
smoke passes this check. A complete paired live trajectory audit remains open
because the functional/environment gates failed.
