# AgentDescriptorV7 Specification V8

`AgentDescriptorV7Codec` is the fixed-width authenticated record used by the
V8 SimplePIR composition. Each physical row is 1,024 bytes:

```text
12-byte random nonce
AES-GCM ciphertext over:
  4-byte canonical JSON length
  schema envelope
  random fixed-width padding
16-byte authentication tag
```

The authenticated envelope binds magic `ATD7`, schema version 7, Agent ID,
capability IDs, publisher key ID, Agent version, placement, optional
Agent-service route descriptor, allowed Tool capabilities, trust class,
catalog epoch, descriptor digest, and Agent-version/catalog-epoch binding.

The Agent-service route descriptor carries route handle, effect semantics,
policy ID, and placement. It contains no executable Python, IR, framework
runtime, or provider implementation.

AAD is domain-separated as `AgentTool|AgentDescriptorV7|catalog_epoch`.
Decoding fails closed on row width, AEAD failure, length/schema/magic/digest/
version-binding error, malformed enums, Agent/service placement disagreement,
expected Agent-ID mismatch, and stale catalog epoch.

Eleven V8 Python tests cover authentication/binding, authenticated malformed
enum/schema rejection, route authorization, all Agent-service effect classes,
profile placement rules, PIR log separation, and delivery-ledger recovery.

