# Stage-6 Baseline Semantics Audit

| Architecture | Trusted components | Authoritative state | Cache/freshness | Revocation and audit | Host view | Deployment change | Fidelity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DIRECT-MODULAR | Mediator and services | Three remote services | None | Current permission; ordered remote append | Semantic endpoint/count/order and stable opaque address | Minimal | Real TCP/process prototype; privacy reference |
| INDEPENDENT-MODULAR-ORAM | Mediator/ORAM client abstraction | Three remote services | ORAM maps/stash proxy | Same current permission/audit | Semantic ORAM endpoint/count/order and paths | Backend change per service | Real wire padding; research ORAM abstraction; privacy reference |
| FIXED-CANONICAL-MODULAR | Mediator/ORAM client abstraction | Three remote services | Fixed schedule, no state cache | Current permission; ordered remote append | Constant semantic endpoint schedule and paths | Preserves service ownership; changes backends/mediator | Executed fixed schedule; compiler has no optimizer saving |
| UNIFIED-ORAM | Mediator/ORAM client abstraction | One unified remote service | Batched preflight | Current permission and ordered append under unified service | One endpoint, generic batched/append operations | Merge databases/ownership and adopt tagged common layout | Executed batching and real padding; research ORAM abstraction |
| HYBRID-P | Mediator plus permission cache | Three remote authorities | Permission cached but validated every action | Zero completed-action stale window; history remote/ordered | Fixed data, validate, history, tool, append schedule | Place policy copy and freshness logic on every client | Correct current semantics; no lease |
| HYBRID-PH | Mediator plus permission/history cache | Three remote authorities | Validate permission and sync history every action | Zero completed-action policy staleness; ordered delta sync and append | Fixed validate/sync schedule; sync response size reveals public update volume | Place global audit copy/sync logic on clients | Correct tested semantics; cache durability omitted |

## Semantic equality findings

- All six return equivalent ALLOW/DENY behavior, reject invalid handles, observe
  DENY→ALLOW, and use the same sanitized tool result.
- All four protected competitors pass next-action revocation, two-device
  visibility, 32-way no-lost-update, and retry idempotency tests.
- Hybrid remote authorities retain the full enterprise state. Their local state
  is a cache; it is not counted as eliminating authoritative server storage.
- Direct and independent modular variants fail the frozen cross-store privacy
  probe (AUC 1.0) and are excluded from the primary Pareto set.

## Privacy equivalence

The fixed structural probe uses the count/sequence of host-visible semantic
endpoints. Fixed canonical, unified, HYBRID-P, and HYBRID-PH score AUC 0.5 and
accuracy 0.5 on 24 balanced episodes; shuffled AUC is 0.5. The two reference
variants score AUC/accuracy 1.0 because an optional history read changes the
observable modular trace.

This rechecks only the frozen Stage-4 channel. Timing and response-size leakage
from real workload variation is not comprehensively classified.

## Accounting fairness

- All remote operations use the same length-prefixed JSON RPC and network
  emulator.
- ORAM rows serialize and transfer their configured ciphertext-padding bytes;
  direct rows do not receive free ORAM protection.
- Unified uses the largest record size in the common tree. It batches preflight
  requests, so it receives the deployment/RTT benefit of one endpoint.
- Hybrid rows pay one validation RPC/action; HYBRID-PH also pays one sync RPC and
  all unseen history bytes.
- Fixed modular issues all privacy slots even when history is not required.
- Trusted-byte values are logical maps/stash/cache accounting, not process RSS.
- Cache durability, authenticated cryptography, disk I/O, and production ORAM
  eviction are omitted for every architecture and called out in the report.

