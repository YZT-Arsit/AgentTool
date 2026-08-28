# Stage-5 Baseline Fairness Audit

## Baseline-by-baseline audit

| Baseline | Why included / design idea | Assumptions | Fidelity | Main possible bias |
| --- | --- | --- | --- | --- |
| MODULAR-ORAM | Stage-4 leakage reference: independently protected semantic stores | One trusted mediator, one observable host | Executed Path-ORAM trace simulator | Natural branch mixture is workload-specific; it is not a privacy-equivalent competitor |
| NAIVE-FIXED | Obvious handwritten worst-case schedule | Same modular trees and public schedule as canonical | Executed; every possible GAAP slot is always accessed | None favorable: it intentionally duplicates canonical work in this schema |
| CANONICAL-MODULAR | Schema/dependency graph compiled to fixed modular schedule | Same host and ORAM model | Executed trace schedule plus analytical byte model | No optimizer benefit exists in this one-action schema |
| UNIFIED-FIXED | One oblivious namespace hides semantic store identity | One tree; largest record determines block size | Executed unified trace; analytical byte accounting | Penalized by deliberately conservative largest-block rule, hence packed variant is also reported |
| UNIFIED-PACKED | Fairer unified representation for heterogeneous records | Fixed 4-KiB pages and hidden packed slot | Conservative analytical packing abstraction | Omits secure packing index, fragmentation dynamics, and contention; can favor unified |
| RANDOMIZED-PARTITION | Tests whether semantic labels, rather than multiple trees, are the issue; inspired by Partition ORAM | Would require private mapping, cache, and oblivious eviction | **NOT IMPLEMENTED** securely. Only functional random remapping exists | Cost excludes a sound eviction protocol; numbers are excluded from privacy-equivalent comparisons |
| HYBRID-P | Keep small permissions trusted | Trusted persistent capacity for permission payload | Executed trace shape; analytical memory/I/O | Omits sealing, freshness, rollback, and recovery overhead, favoring hybrid |
| HYBRID-PH | Keep permissions and history trusted | Larger trusted persistent capacity | Executed trace shape; analytical memory/I/O | Same omission is material as history grows |
| SCAN-* | Simple fixed full scans for small stores | Sequential full-store transfer; fixed schedule | Executed fixed scan marker plus analytical byte model | Scan CPU/cache time is not executed, favoring scans in latency estimates |

The randomized design is conceptually compared against classic Partition ORAM,
whose design includes client-side caching/background eviction and randomized
partition assignment; this repository does not reproduce that protocol. See
[Stefanov, Shi, and Song, Partition ORAM](https://arxiv.org/abs/1106.3652).

## Cross-cutting fairness checks

### Block-size and packing fairness

Modular stores independently round their own record sizes to a power-of-two
block. `UNIFIED-FIXED` uses the largest block; `UNIFIED-PACKED` prevents that
choice from being the sole reason modular wins. Packing metadata is charged at
16 B per record. The packed variant is still analytical and should be viewed as
a sensitivity bound, not a completed backend.

### Trusted-memory fairness

All outsourced designs include the same 4-B-per-block position-map and six-
block stash proxies. Hybrids additionally charge exact raw trusted payload
bytes. The comparison does **not** charge persistent sealing/checkpointing,
which systematically favors hybrids; reports therefore make hybrid
recommendations conditional on a suitable trusted persistence mechanism.

### Server and trust assumptions

Every valid primary competitor uses one honest-but-curious host and a trusted
mediator. No result assumes two non-colluding servers or trusted hardware. A
real deployment may use a TEE, but this simulator neither requires nor models
TEE side channels.

### Network and parallelism assumptions

LOCAL/DATACENTER/REMOTE values are synthetic what-if profiles, never
measurements. Modular parallelism uses only fixed public rounds. Unified paths
are serialized through one tree. Server queueing, cryptography, disk seeks,
batching, and concurrency are omitted uniformly; scan CPU omission is called
out separately.

### Privacy equivalence

The strongest Stage-4 binary hidden-branch probe is rerun with random and
grouped-entity splits. MODULAR-ORAM is a leakage reference. Fixed modular,
unified, hybrid, and scan shapes are constant and score at chance. The
randomized-remap classifier also scores near chance, but this cannot substitute
for a sound oblivious-eviction argument and does not upgrade that baseline from
`NOT IMPLEMENTED`.

### Functional equivalence

The automated suite compares authorized/denied decisions, private synthetic
value resolution, disclosure update, and synthetic tool outcome across all
executed variants. It passes. This establishes simulator-level semantics, not
protocol security or crash-consistent persistence.

## Optional baselines omitted

An oblivious relational engine was omitted because a faithful engine and query
planner would add substantial unrelated infrastructure. ObliDB is not claimed
or approximated. Credential state was also omitted from the primary result to
keep the workload limited to the three source-supported GAAP-derived stores.
