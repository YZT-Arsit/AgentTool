# Stage-7 Concurrency Audit

## ORAM coordination

All clients of one authoritative ORAM share a single trusted coordinator and
one position map/stash/version state. A mutex serializes complete ORAM
transactions. Independent clients are not allowed to maintain divergent maps.
Fixed modular owns one coordinator per semantic store; Unified owns one global
coordinator; the hybrids coordinate only their outsourced domains.

**Yes, multi-client ORAM introduces a centralized trusted coordination
component, and yes, this materially changes the deployment/trust story.** It
can be deployed as the already-trusted mediator state service, but availability,
leader recovery, and serialization are now explicit system requirements.

## Measured contention

One action uses the Stage-7 architecture-specific secure access schedule. The
local full-tree checkpoint dominates these results.

| Architecture | Clients | Throughput actions/s | p95 latency | Mean coordinator wait |
|---|---:|---:|---:|---:|
| Fixed canonical modular | 1 | 17.8 | 53.4 ms | 0.005 ms |
| Fixed canonical modular | 32 | 19.1 | 1,641.0 ms | 1,124.8 ms |
| Unified ORAM | 1 | 7.6 | 131.4 ms | 0.007 ms |
| Unified ORAM | 32 | 7.6 | 4,157.8 ms | 3,674.5 ms |
| Hybrid-P | 1 | 16.2 | 61.5 ms | 0.005 ms |
| Hybrid-P | 32 | 17.6 | 1,772.4 ms | 1,292.0 ms |
| Hybrid-PH | 1 | 28.5 | 34.7 ms | 0.002 ms |
| Hybrid-PH | 32 | 30.9 | 992.2 ms | 748.7 ms |

The nearly flat throughput and rapidly increasing tail/wait time demonstrate
the serialization bottleneck. Unified has one recovery domain but the largest
critical section and blast radius. Fixed modular permits cross-store
parallelism in principle, though the tested canonical action waits on its
required domains. Hybrid-PH has the smallest outsourced critical section but
retains cache synchronization obligations.

## History and multi-device semantics

The authoritative disclosure log serializes appends under one lock, assigns a
monotonic version, and de-duplicates by event/operation ID. Stress tests at 2,
8, and 32 concurrent appenders had no missing events, duplicates, or version
gaps. Service-object restart preserves the synthetic authority and disclosure
log state.

An offline Hybrid-PH device restores an invalid cache and fetches all events
after its last version before using history. Hybrid-P keeps history
authoritative remotely and therefore avoids local history rebuild growth.

## Deployment limitation

The coordinator and append service are single-process local prototypes, not a
distributed consensus implementation. Horizontal scale requires a single
leader or linearizable state manager, durable fencing/leases, and failover that
preserves the same position map and freshness root.
