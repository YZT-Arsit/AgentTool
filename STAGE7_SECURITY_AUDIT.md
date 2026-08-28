# Stage-7 Production Feasibility and Security Audit

## 1. Executive decision

**STAGE-7 SECURITY DECISION: FEASIBLE WITH TRUST/DEPLOYMENT CONSTRAINTS.**

No structural blocker was found in the declared local model. All four
privacy-equivalent architectures can preserve integrity, freshness, crash
atomicity, current authorization, ordered history, and effect/audit recovery.
They do so only with a non-rollbackable trusted freshness root, durable ORAM
client state, serialized authoritative coordination, and an idempotent/queryable
tool interface. The implementation is a research feasibility prototype, not a
production security implementation.

## 2. Frozen threat model

The planner is untrusted; the mediator and ORAM client state are trusted;
enterprise state is authoritative; the infrastructure host is
honest-but-curious for confidentiality. Active storage corruption/replay is
injected only to audit detection and recovery. The experiment remains fully
local and synthetic. It does not address network destination privacy, malicious
tools, full trajectory privacy, TEE side channels, real credentials, or real
authorization systems.

## 3. Storage-security upgrade

Stage 7 adds authenticated physical envelopes, signed checkpoints, versioned
copy-on-write server trees, trusted root binding, runtime-generated keys,
journaling, and invariant-checked recovery. Because no standard AEAD library is
installed, HMAC-SHA-256 integrity is layered over the prior confidentiality
abstraction. Authenticated storage is therefore **PARTIAL** at a production
boundary even though all local integrity injections were detected.

## 4. Authenticated block format

Each envelope authenticates domain/context, opaque physical slot, epoch,
per-bucket version, and sealed payload. The payload internally contains block
and value data; logical identifiers are not host-visible. Checkpoint/root keys
are label-derived separately from block tags. Errors collapse to generic
verification/invariant failures.

## 5. Freshness / rollback protection

The trusted checkpoint binds the current epoch, transaction ID, active tree,
authenticated root, every bucket version, position map, stash, and geometry.
Old block, bucket, tree, permission, and disclosure snapshots were detected in
all four architectures. Rotation produced a fresh key/epoch and rejected the
old tree. This is a conditional PASS: rollback of the trusted root together
with server state is outside the implemented protection and requires a real
non-rollbackable anchor.

## 6. Durable ORAM client state

Keys, position map, stash, epoch/version map, root/checkpoint, and pending
journal are durable. Measured trusted persistent totals were:

| Architecture | Keys | Position map | Cache | Epoch/version | Journal/checkpoint | Total |
|---|---:|---:|---:|---:|---:|---:|
| Fixed canonical modular | 96 B | 640 B | 0 B | 1,292 B | 4,414 B | 6,640 B |
| Unified ORAM | 32 B | 640 B | 0 B | 2,052 B | 6,212 B | 9,002 B |
| Hybrid-P | 64 B | 512 B | 128 B | 1,032 B | 3,399 B | 5,267 B |
| Hybrid-PH | 32 B | 256 B | 2,688 B | 516 B | 1,699 B | 5,257 B |

These exact values describe the small configured prototype; position maps,
checkpoints, and Hybrid-PH history caches grow with deployment size.

## 7. Crash consistency

The commit point is atomic replacement of the signed trusted checkpoint. Seven
injected points at or before server write rolled back; a crash after checkpoint
before acknowledgment completed. All 32 architecture/point combinations
recovered the expected value and passed invariants. A terminated child process
also restarted safely. This validates the old-or-new protocol under local
filesystem assumptions, not distributed storage durability.

## 8. Position-map/stash recovery

Position map and stash are checkpointed with the tree root and transaction.
Restart reconstructed both byte-for-byte at the logical level and recovered all
written values. Recovery rejected disappearance, duplication, stale placement,
root mismatch, and Path ORAM invariant failure.

## 9. Hybrid cache recovery

Restored caches start invalid. Hybrid-P remotely revalidates permission;
Hybrid-PH revalidates permission and synchronizes history after its stored
version. A service error leaves the cache invalid and returns DEFER. The
synthetic authority itself now persists permission/version/history and survives
service-object restart.

## 10. Permission revocation after restart

Both hybrid cases cached ALLOW, advanced authoritative policy to version 2/DENY,
restored the stale snapshot, restarted, and returned DENY. Hybrid-P recovery
used 74 bytes, one RTT, and 0.005 ms locally; Hybrid-PH used 212 bytes, two RTTs,
and 0.008 ms. No stale cache value authorized an action.

## 11. Cross-device history recovery

Device A appended while Device B held an old offline Hybrid-PH snapshot. On
restart, B fetched the version delta and recovered the missing event before a
history-dependent decision. Hybrid-P keeps history authoritative remotely and
does not restore a local history cache.

## 12. Concurrent history updates

At 2, 8, and 32 concurrent appenders, unique event IDs, a lock, monotonic
versions, and idempotent append produced no lost writes, duplicates, or version
gaps. This is a local linearizable service abstraction; distributed deployment
still needs a linearizable database/leader rather than process-local locking.

## 13. Effect/log atomicity

The mediator journals PREPARE, creates an audit PREPARED record, invokes the
tool, and commits the audit after the effect. Because this is a saga rather than
a shared transaction, recovery queries the effect by operation ID and commits
or aborts the audit deterministically. All four required failure orderings ended
with a matching effect/audit state.

## 14. Idempotent retry

The mock tool persists operation outcomes and binds the ID to a SHA-256 payload
digest. Exact retries return the prior result; a conflicting payload fails.
Crash and timeout retries each produced one effect. The contract must be
provided by a real tool endpoint for the guarantee to transfer.

## 15. Failure injection

All 44 architecture/integrity cases detected ciphertext/tag/version corruption,
missing/duplicate blocks, old blocks/buckets/trees, stale permission/history,
and key-rotation replay. Local timeout, drop, delay, unavailable service,
duplicate response, and process termination paths were also exercised.
Authorization failed closed when current permission could not be established.
See `FAILURE_INJECTION_REPORT.md` and `FAILURE_MATRIX.csv`.

## 16. Multi-client ORAM coordination

A single trusted coordinator owns each authoritative ORAM's position map,
stash, epoch, and lock. Independent clients cannot safely own divergent copies.
Thus **multi-client ORAM does require central trusted coordination, and that
materially changes deployment** by adding serialization, availability, fencing,
and failover obligations. Unified has one global coordination/recovery domain;
fixed modular has three smaller domains; the hybrids coordinate outsourced
subsets.

At 32 clients, throughput was 19.1/7.6/17.6/30.9 actions/s and p95 latency was
1.64/4.16/1.77/0.99 seconds for Fixed/Unified/Hybrid-P/Hybrid-PH. Mean wait was
1.12/3.67/1.29/0.75 seconds. Full-tree checkpointing makes these bottlenecks
deliberately visible.

## 17. Recovery privacy

Recovery performs a full physical tree scan and exposes no logical ID or
real/dummy field. It preserves the evaluated address privacy but visibly reveals
the recovery event, domain, and tree size. Result: **LIMITED additional
leakage**, or PARTIAL rather than full failure-obliviousness.

## 18. Normal-path overhead

| Architecture | Hardened mean | Baseline mean | Increase | Durable writes/action | Server amplification |
|---|---:|---:|---:|---:|---:|
| Fixed canonical modular | 54.44 ms | 0.046 ms | 1,177x | 123,713 B | 25.1x |
| Unified ORAM | 72.61 ms | 0.110 ms | 658x | 502,685 B | 37.0x |
| Hybrid-P | 41.72 ms | 0.037 ms | 1,119x | 101,987 B | 23.2x |
| Hybrid-PH | 20.33 ms | 0.020 ms | 1,015x | 50,869 B | 23.2x |

The cross-architecture milliseconds and bytes are useful; the multiplier is
mostly the difference between an in-memory simulator and an intentionally
simple full-tree durable checkpoint. It must not be presented as expected
production AEAD overhead.

## 19. Failure/recovery overhead

Aggregate restart read 68,790/100,911/50,934/25,405 bytes and took
6.54/5.66/4.28/2.04 ms for Fixed/Unified/Hybrid-P/Hybrid-PH. Recovery wrote no
new server tree. Crash-point-specific recovery remained below 1.4 ms for the
single small domain used in injection. Effect reconciliation took 8.2–13.4 ms.
Steady-state and failure-path values are reported separately.

## 20. Trusted persistent state

Unified needs only one key/coordinator/checkpoint domain but has the largest
measured checkpoint and total trusted bytes. Fixed has three independently
recoverable domains and more keys, but corruption blast radius is one semantic
service. Hybrid-P has two outsourced domains plus a bounded policy cache.
Hybrid-PH has the smallest outsourced domain but its trusted history cache and
restart synchronization grow with unseen global history.

## 21. Architecture comparison

- **Fixed canonical modular:** preserves enterprise ownership and limits
  corruption blast radius; pays three recovery/coordination domains and fixed
  padded work.
- **Unified ORAM:** simplest recovery and consistency mechanism count; central
  global lock, widest corruption blast radius, highest measured trusted/server
  bytes, and strongest deployment coupling.
- **Hybrid-P:** bounded cache, no history rebuild, two outsourced domains, and
  the best balance for active shared history; requires per-action permission
  freshness.
- **Hybrid-PH:** lowest small-workload path cost; greatest cache/sync sensitivity
  and most complex stale-restore semantics.

Authenticated storage does not materially alter the Stage-6 privacy/performance
Pareto ordering because all protected paths need it. Crash/recovery requirements
do materially alter the production-security subranking by favoring fewer
recovery domains and penalizing cached history, though Hybrid-P remains the
recommended default.

## 22. Production-readiness matrix

The required qualitative matrix is in `PRODUCTION_READINESS_MATRIX.csv`.
Privacy, authorization correctness, freshness, crash consistency,
multi-device semantics, concurrency safety, and effect idempotency pass in the
local model. Rollback protection is PARTIAL until the freshness anchor is
productionized; audit consistency is PARTIAL until real tools and distributed
logs implement the contract. Trusted-state, recovery, and deployment cells
distinguish architecture-specific burdens without inventing scores.

## 23. Structural blockers

**None found.** The central coordinator and freshness root are material
constraints, not contradictions: both may live inside the declared trusted
mediation/control plane. Full-tree copy-on-write is not scalable, but it is a
replaceable checkpoint strategy rather than a privacy impossibility. A tool
without idempotency/query support would be a blocker for exact effect/audit
reconciliation for that tool, so such tools require compensation or weaker
semantics.

## 24. Recommended architecture

**HYBRID-P.** It retains authoritative shared history, has bounded cache
recovery, rejects stale permission through remote validation, uses fewer
outsourced recovery domains than fixed modular, and avoids Unified's global
failure/lock domain. Fixed canonical remains appropriate where organizational
store ownership dominates; Unified is attractive when centralized coupling is
already acceptable and recovery simplicity matters most; Hybrid-PH is limited
to bounded, low-churn histories.

## 25. Remaining limitations

Production AEAD/KMS, a non-rollbackable freshness service, scalable incremental
checkpointing, coordinator leader failover/fencing, distributed append
linearizability, real storage durability, and tool-specific idempotency/query
contracts are not implemented. The test scale is small and local; latency is
single-run system evidence, not a benchmark confidence interval. Denial of
service and trusted-component compromise remain outside scope. No further
synthetic privacy classifier experiment is warranted; implementation/security
boundaries can now freeze for design review.

## Mandatory final questions

| Question | Answer |
|---|---|
| Q1. Can authenticated outsourced state detect block tampering? | **YES**, in the implemented integrity model |
| Q2. Can it detect stale/replayed state? | **YES**, assuming the trusted root is not rolled back |
| Q3. Can ORAM recover safely from all injected crash points? | **YES** |
| Q4. Can position map and stash be durably recovered? | **YES** |
| Q5. Can HYBRID-P reject a revoked permission after restoring an old local cache? | **YES** |
| Q6. Can HYBRID-PH recover current cross-device disclosure history after restart? | **YES** |
| Q7. Can concurrent disclosure-log updates avoid lost writes? | **YES** |
| Q8. Can duplicate or ambiguous tool retries avoid duplicate effects? | **YES** |
| Q9. Can successful effects be reconciled with missing/uncertain audit commits? | **PARTIAL**: yes locally; requires the real tool/log contract |
| Q10. Does multi-client ORAM require a centralized coordination component? | **YES** |
| Q11. Does that coordination materially change the deployment/trust model? | **YES** |
| Q12. Does recovery introduce additional privacy leakage? | **LIMITED**: event/domain/size, not logical ID |
| Q13. Does authenticated storage materially change the Stage-6 Pareto ranking? | **NO** |
| Q14. Does crash/recovery complexity materially change the architecture ranking? | **YES**, the production-security subranking changes |
| Q15. Which architecture has the smallest production-security burden? | **UNIFIED-ORAM for mechanism/recovery count**, at the cost of global coupling and blast radius |
| Q16. Which architecture provides the strongest enterprise semantics at acceptable cost? | **HYBRID-P** |
| Q17. Is the research system production-feasible under the declared threat model? | **WITH CONSTRAINTS** |
| Q18. Is another synthetic privacy experiment required? | **NO** |
| Q19. Can implementation/security boundaries now be frozen? | **YES**, for the research prototype, not deployment |

