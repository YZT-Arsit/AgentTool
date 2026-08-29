# Canonical Dataflow — V9

Status: **COMPONENT PATHS EXECUTABLE; FULL COMPOSITION NOT YET EXECUTABLE**

```text
private capability -> V8 TrustedPIRClient -> official SimplePIR
-> authenticated AgentDescriptorV7 -> placement/effect policy
-> TrustedActionRouter -> RFC9292 BHTTP -> RFC9458 client
-> local Relay -> RFC9458 Gateway -> private route -> local provider
-> durable result/recovery -> prepared current-slot OHTTP response
-> Relay -> OHTTP client -> BHTTP decode -> DeliveryLedger
-> framework-visible result
```

Validated component chains now include:

- official SimplePIR -> authenticated AgentDescriptorV7: 4/4 fresh post-OHTTP
  smoke queries;
- RFC9292 -> RFC9458 -> frozen V8 Relay -> RFC9458 -> RFC9292: 2/2 loopback
  rounds;
- V8 routing/effect/placement/ledger regression: 11/11.

No single command yet composes every arrow. The canonical functional gate
therefore remains blocked rather than inferring success from component tests.

