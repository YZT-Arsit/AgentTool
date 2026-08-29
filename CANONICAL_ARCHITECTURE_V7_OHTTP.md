# Canonical Architecture V7-OHTTP

## Status

This document defines the canonical architecture, but the RFC 9458 wire is
`NOT_IMPLEMENTED_OFFLINE` in the current checkout. The executable custom
AES-GCM transport is retained only as `LEGACY_DEV_TRANSPORT`; its earlier
results are pre-OHTTP engineering evidence.

```text
orthogonal protected Agent/LLM pipeline
  -> ProtectedActionIntent
  -> TrustedActionModule / future TEE
  -> official SimplePIR AgentDescriptor lookup
  -> private authorization and ActionRouteDescriptor resolution
  -> fixed padded RFC 9292 Binary HTTP request
  -> RFC 9458 OHTTP client encapsulation
  -> opaque Cloud Relay
  -> trusted external OHTTP Action Gateway
  -> private route-handle resolution
  -> one real Tool or external Agent service

provider result
  -> durable effect/result journal
  -> bounded private ready queue
  -> next eligible pre-existing public response slot
  -> fixed padded Binary HTTP response
  -> slot-local OHTTP response encapsulation
  -> TrustedActionModule
```

The IR is absent. FHE, MPC, PSI, and ORAM are absent from the action transport.
Official SimplePIR remains solely the private Agent-descriptor lookup.

## Public slot contract

Each slot is one unary OHTTP request/response exchange. The request contains a
REAL action or NOOP. The response contains one eligible queued RESULT or WAIT.
A result created in slot `j` may be delivered in slot `k > j`; its operation ID
is application data inside slot `k`'s encrypted response. Slot `j`'s OHTTP
response context is never reused.

The public profile fixes session count/lifetime, slot count and order, request
cadence, response deadline/lag, encapsulated request length, encapsulated
response length, Relay endpoint, and Gateway endpoint. Completion cannot add a
slot, change a length, reconnect, or extend the public lifetime.

## Trusted and untrusted roles

- Trusted module/future TEE: selected Agent ID and descriptor, private route
  map, route handle, protected action plaintext, authenticated Gateway public
  key configuration, OHTTP client and response contexts.
- Cloud Relay: exact opaque-byte forwarding and public metadata only.
- Trusted Action Gateway: OHTTP private keys, decapsulation, authorization,
  private route resolution, worker plane, effect journal, ready queue, and
  response encapsulation.
- Provider: learns its own invocation. V7-OHTTP does not hide an invocation
  from that provider.

## Preserved reliability substrate

The V7 admission/capacity proof, durable multi-result queue, out-of-order
eligible selection, effect journal, restart replay, and duplicate suppression
remain mandatory. They are transport-independent. The pre-OHTTP Linux gate
delivered 161/161 admitted results across 1/10/50/100-operation runs; this
supports the reliability substrate, not the RFC 9458 wire.

