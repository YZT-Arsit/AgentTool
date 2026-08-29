
# Canonical Runner V9 Dataflow

```text
private capability
  -> official SimplePIR query/server answer/client recovery
  -> authenticated AgentDescriptorV7
  -> TrustedActionRouter authorization
  -> private opaque route_handle
  -> RFC9292 known-length request
  -> fresh RFC9458 request + client context k
  -> local opaque Relay
  -> Gateway decapsulation + server context k
  -> RFC9292 decode + trusted private route map
  -> asynchronous local provider
  -> fsync-backed EffectRecoveryJournal RESULT_COMMITTED
  -> durable ready queue
  -> bounded in-memory publication before preparation boundary
  -> RFC9292 response + current server context k
  -> immutable PreparedSlot
  -> Relay
  -> current client context k + RFC9292 decode
  -> DeliveryLedger
  -> framework-visible sink
```

NOOP enters the same request path but performs zero provider operations. Result selection is independent of the submitting round; an older completed operation can use the current round's fresh response context.
