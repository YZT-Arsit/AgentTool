# Stage-5 Privacy–Systems Trade-off Report

## 1. Executive decision

**CONFIGURATION-DEPENDENT PARETO FRONTIER**

No privacy-valid architecture dominates across bandwidth, trusted memory,
latency, persistence burden, and simplicity. With a 16-MiB trusted-memory
budget, `HYBRID-PH` minimizes modeled transfer in S, M, and H, while `HYBRID-P`
wins L because the 34.0-MiB raw permission-plus-history state does not fit.
Canonical modular is substantially cheaper than unified packing in the
heterogeneous Stage-5 regimes, but the equal-record GAAP control reproduces a
case where unpadded unified is cheaper. Canonical and naive fixed have exactly
the same schedule and analytical cost, so no schema-compiler optimization
advantage was demonstrated.

## 2. Frozen privacy claim

Stage 5 does not broaden the Stage-4 claim:

> In modular privacy-preserving agent runtimes where heterogeneous private and
> security-state services remain distinguishable to the host, protecting each
> service's logical addresses independently can leave cross-store mediation
> structure visible. Canonical modular schedules and a unified oblivious
> address space both suppress the evaluated channels, with
> configuration-dependent systems trade-offs.

This remains conditional on the separately observable-store deployment. The
PAuth-derived Stage-4 negative evidence remains in scope: its single protected
state service did not instantiate this cross-store channel. Stage 5 does not
claim that ORAM is generally insufficient or that all agent runtimes leak.

## 3. Architectures compared

| Architecture | Status | Outsourced organization |
| --- | --- | --- |
| MODULAR-ORAM | leakage reference | Three semantic Path-ORAM services |
| NAIVE-FIXED | privacy pass | Handwritten four-slot modular schedule |
| CANONICAL-MODULAR | privacy pass | Schema-derived four-slot modular schedule |
| UNIFIED-FIXED | privacy pass | One tree, largest record determines block size |
| UNIFIED-PACKED | privacy pass | One analytical 4-KiB packed namespace |
| RANDOMIZED-PARTITION | **NOT IMPLEMENTED securely** | Functional random-remap abstraction only |
| HYBRID-P | privacy pass | Permission trusted; data/history outsourced |
| HYBRID-PH | privacy pass | Permission/history trusted; data outsourced |
| SCAN-* | privacy pass | Data ORAM plus fixed security-store scans |

All valid primary comparisons use one trusted mediator and one
honest-but-curious observable host. No two-server assumption is introduced.

## 4. Source-grounded GAAP-derived workload

The workload reuses Stage 4's abstraction of the three persistent components
documented by [GAAP](https://arxiv.org/abs/2604.19657): private user data,
persistent disclosure permissions, and disclosure history. A synthetic
`SEND_MESSAGE` action performs private-value resolution, permission evaluation,
history consultation/update, and an authorized or denied synthetic disclosure.
No credential store or other synthetic persistent service is added to the
primary experiment.

The exact semantic accesses are produced by the mediator. Records, handles,
values, authorization outcomes, and tool outcomes are fully synthetic and
local.

## 5. Privacy equivalence check

The strongest hidden-branch probe was rerun over 4,000 episodes per seed for
seeds 0/1/2. Chance AUC is 0.5.

| Architecture class | Random-split AUC, mean ± SD | Grouped-entity AUC, mean ± SD | Shuffled accuracy | Decision |
| --- | ---: | ---: | ---: | --- |
| MODULAR-ORAM | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.511 / 0.510 | leak reference |
| Fixed/unified/hybrid/scan variants | 0.500 ± 0.000 | 0.500 ± 0.000 | 0.493 / 0.484 | pass |
| Random-remap abstraction | 0.504 ± 0.014 | 0.499 ± 0.016 | 0.508 / 0.505 | **NOT IMPLEMENTED** |

Near-chance classification is only a sanity check. It cannot repair the missing
security machinery in the random-remap abstraction. The automated functional
test confirms identical authorized/denied decision, synthetic private value,
disclosure update, and tool outcome across executed variants. All 23 tests pass.

## 6. Byte-aware cost model

The medium-regime primary table uses data/permission/history counts of
8,192/1,024/4,096 and record sizes of 4,096/128/256 B. Latency is measured
Python simulator latency; bytes and storage are analytical.

| Architecture | Privacy | Trusted bytes | Bytes/action | p95 µs | Storage amp. | Fixed parallel rounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MODULAR-ORAM | leak | 77,824 | 280,576 | 111.3 | 8.00× | 3 |
| NAIVE-FIXED | pass | 78,080 | 523,264 | 133.9 | 8.00× | 3 |
| CANONICAL-MODULAR | pass | 78,080 | 523,264 | 135.3 | 8.00× | 3 |
| UNIFIED-FIXED | pass | 77,824 | 1,474,560 | 218.6 | 15.46× | 3 |
| UNIFIED-PACKED | pass | 58,588 | 1,474,560 | 219.8 | 15.46× | 3 |
| RANDOMIZED-PARTITION | not implemented | 126,612 | 2,359,296* | 161.4* | 15.45×* | 6* |
| HYBRID-P | pass | 204,800 | 512,000 | 107.4 | 7.97× | 2 |
| HYBRID-PH | pass | 1,236,992 | 458,752 | 35.3 | 7.73× | 1 |
| SCAN-PERMISSION | pass | 73,728 | 643,072 | 108.1† | 7.97× | 3 |
| SCAN-HISTORY | pass | 61,440 | 2,567,168 | 61.5† | 7.79× | 3 |
| SCAN-BOTH | pass | 57,344 | 2,686,976 | 36.1† | 7.76× | 3 |

`*` Excluded lower-bound abstraction. `†` The microbenchmark executes a fixed
scan marker, not the full byte scan; use modeled I/O, not these p95 values, to
compare scans.

The same rows report all requested metrics in `cost_matrix.csv`. For example,
canonical has 4 logical accesses, 4 paths, 408 bucket blocks (127.75 4-KiB byte
equivalents), 53,248 B of position maps, a 24,576-B stash proxy, 25% dummy work,
and 8.00× server-storage amplification. The modular trees have heights
13/10/12 and blocks 4,096/128/256 B. Unified uses one height-14, 4-KiB tree.

## 7. Modular vs unified

The Stage-4 equal-record control is reproduced exactly by the Stage-5 path
formula:

| GAAP matched control | Logical paths | Physical blocks | Bytes/action |
| --- | ---: | ---: | ---: |
| Canonical modular | 4 | 368 | 1,507,328 |
| Unified unpadded | 3 | 312 | 1,277,952 |
| Unified padded | 4 | 416 | 1,703,936 |

Thus unified unpadded is 15.2% cheaper in transfer than canonical when all
records are 4 KiB and unified needs only three paths. Padding is unnecessary for
the evaluated unified trace and would reverse the result. In the Stage-5
heterogeneous baseline, modular's small permission/history blocks outweigh the
one extra path: canonical transfers 0.50 MiB versus 1.41 MiB for unified packed.

## 8. Naive fixed vs schema-driven canonical

Both execute data-read, permission-read, history-read, and history-write in the
same fixed schedule. They are identical in logical accesses (4), dummy fraction
(0.25), physical bytes (523,264), serial paths (4), and fixed parallel rounds
(3). Mean/median/p95 simulator latency was 103.0/100.0/133.9 µs for naive and
104.2/100.4/135.3 µs for canonical; this small Python timing variation is not a
work reduction and was not treated as an architectural saving.

**Schema-driven optimization advantage not demonstrated.** The compiler remains
a specification/automation mechanism in this workload, not a measured systems
contribution.

## 9. Randomized partitioned backend

The implemented object preserves values, privately remaps records, passes
mapping invariants, and produces near-chance traces for the selected classifier.
It is not a sound Partition ORAM: it exposes an old-partition read followed by a
new-partition write and omits the client cache and oblivious/background eviction
needed to prevent linkability across accesses. Classic Partition ORAM includes
those mechanisms ([Stefanov, Shi, and Song](https://arxiv.org/abs/1106.3652)).

Therefore Q4 is answered `NOT IMPLEMENTED`, and the six-path/2.25-MiB medium
estimate is excluded from winners and figures. The excluded estimate uses eight
height-11 partitions, 576 transferred bucket blocks, six serial rounds, 102,036
B of position/partition maps, a 24,576-B stash proxy, and no background-eviction
charge. The last omission is exactly why it is not a fair secure cost. It would
be scientifically invalid to infer either a partitioned advantage or
disadvantage from it.

## 10. Trusted-state hybrid

At M, raw trusted PermissionDB state is 131,072 B; PermissionDB plus
DisclosureLog is 1,179,648 B. Including outsourced position maps and stash,
total proxies are 204,800 B for HYBRID-P and 1,236,992 B for HYBRID-PH.
HYBRID-PH has the lowest external transfer and measured simulator latency when
it fits. HYBRID-P is the safer large-history choice.

This advantage is conditional: real persistent trusted state needs sealing,
freshness/rollback protection, checkpointing, and recovery. Those costs were
not implemented and would weaken the hybrid result.

## 11. Fixed-scan crossover

At the baseline 128-B record size, a fixed permission scan beats canonical
modular through 128 records under LOCAL, 64 under DATACENTER, and 32 under
REMOTE. The same thresholds hold for 128-B history entries; history uses two
full scans for read/update. Across sizes, maximum winning counts are:

| Record bytes | LOCAL | DATACENTER | REMOTE |
| ---: | ---: | ---: | ---: |
| 64 | 256 | 128 | 32 |
| 128 | 128 | 64 | 32 |
| 256 | 128 | 64 | 32 |
| 512 permission | 64 | 64 | 32 |
| 1,024 history | 64 | 32 | 32 |

These are grid endpoints from the fixed profiles, not continuous analytic
roots. Since scan CPU/cache cost is omitted, they are optimistic for scans.

## 12. Store-size heterogeneity

With PermissionDB=1,024 and DisclosureLog=4,096, increasing the
data-to-security count ratio from 1 to 256 raises canonical transfer from
490,496 to 752,640 B. Unified packed rises from 1,376,256 to 2,162,688 B.
Canonical is cheaper throughout this sweep because independently sized blocks
avoid moving 4 KiB for small security records. This is a meaningful modular
advantage, but it is not universal because the equal-record control favors
unified.

## 13. Record-size heterogeneity

Canonical modular was cheaper than unified packed in all 48 Stage-5 record-size
combinations. At 16-KiB data and 64-B permission/history records, canonical is
1,853,952 B/action, unified fixed is 5,898,240 B, and unified packed is
2,211,840 B. Packing narrows the gap substantially but does not remove it. At
512/64/64 B, canonical is 76,288 B versus 1,179,648 B for the fixed 4-KiB packed
page model. These outcomes show why block-count-only comparison is misleading.

## 14. Disclosure-log growth

At 64/4,096/262,144 history records, canonical transfer is
498,688/523,264/547,840 B. HYBRID-PH remains 458,752 B externally, but total
trusted state grows from 204,800 B to 1,236,992 B to 67,297,280 B. With a 16-MiB
budget, the preferred hybrid changes from HYBRID-PH to HYBRID-P at 65,536
history records. Fixed history scan grows from 502,784 B to 2,567,168 B to
134,687,744 B. History growth therefore changes both feasibility and ordering.

## 15. Read/write mix

| Mix | Canonical | Unified packed | HYBRID-P | HYBRID-PH |
| --- | ---: | ---: | ---: | ---: |
| Read-heavy | 481,997 B | 1,204,224 B | 470,733 B | 458,752 B |
| Balanced | 509,952 B | 1,720,320 B | 498,688 B | 458,752 B |
| Write-heavier | 549,888 B | 2,457,600 B | 538,624 B | 458,752 B |

Path ORAM already models a full-path read/write transfer for either operation;
write sensitivity comes from access frequency plus a 15% proportional compute
uplift. HYBRID-PH's history work stays trusted, so external transfer is stable.
The uplift is analytical, not a measured write engine.

## 16. Trusted-memory consumption

Raw security payload and lowest-transfer choices are:

| Regime | Permission | Permission + history | 1-MiB winner | 16-MiB winner | 64-MiB winner |
| --- | ---: | ---: | --- | --- | --- |
| S | 16 KiB | 80 KiB | HYBRID-PH | HYBRID-PH | HYBRID-PH |
| M | 128 KiB | 1.125 MiB | HYBRID-P | HYBRID-PH | HYBRID-PH |
| L | 2 MiB | 34 MiB | NAIVE/CANONICAL tie | HYBRID-P | HYBRID-PH |
| H | 64 KiB | 2.063 MiB | HYBRID-P | HYBRID-PH | HYBRID-PH |

The fitting decision uses raw trusted payload; reported total architecture
memory additionally charges outsourced maps/stash. Budget sweeps at
1/4/16/64/256 MiB are in `trusted_memory_crossover.csv`.

## 17. Parallelism

Canonical has four serial paths but three fixed privacy-safe rounds; HYBRID-P
has three paths and two rounds; HYBRID-PH has one. Unified has three paths and
three rounds through its single tree. At the REMOTE profile, canonical falls
from 41.0 ms serial to 36.0 ms parallel and HYBRID-P from 35.5 to 30.5 ms.
Parallelism is therefore material at high RTT, although canonical does not gain
an extra round over three-path unified in this schema.

## 18. Measured latency

Across three seeds, medium-workload mean/median/p95 simulator latency in µs was:

| Architecture | Mean | Median | p95 |
| --- | ---: | ---: | ---: |
| Naive fixed | 103.0 | 100.0 | 133.9 |
| Canonical modular | 104.2 | 100.4 | 135.3 |
| Unified fixed | 155.7 | 150.4 | 218.6 |
| Unified packed trace | 156.0 | 150.6 | 219.8 |
| HYBRID-P | 80.2 | 77.4 | 107.4 |
| HYBRID-PH | 23.2 | 22.1 | 35.3 |

These measure Python trace mechanics, not cryptography, disk, network, actual
packed pages, or scan bytes. They support internal relative complexity only.

## 19. Modeled deployment latency

| Architecture | LOCAL serial/parallel ms | DATACENTER serial/parallel ms | REMOTE serial/parallel ms |
| --- | ---: | ---: | ---: |
| Canonical | 0.511 / 0.506 | 2.965 / 2.765 | 41.003 / 36.003 |
| Unified packed | 1.249 / 1.249 | 6.552 / 6.552 | 74.036 / 74.036 |
| HYBRID-P | 0.479 / 0.474 | 2.702 / 2.502 | 35.534 / 30.534 |
| HYBRID-PH | 0.390 / 0.390 | 2.053 / 2.053 | 23.368 / 23.368 |

These are what-if calculations, not measurements. Their units use bandwidth in
bytes/ms (`Mb/s * 125`), plus RTT and the local compute proxy.

## 20. Pareto frontier

The practical Pareto set is configuration-dependent:

- `HYBRID-PH` when trusted persistent capacity and its operational protections
  are acceptable.
- `HYBRID-P` when permission fits but growing history does not.
- `NAIVE-FIXED` / `CANONICAL-MODULAR` as an equal-cost point when state remains
  outsourced and record/store heterogeneity matters; canonical has no measured
  optimizer advantage here.
- Unpadded unified (and potentially secure packed unified) when access-count
  reduction and homogeneous records outweigh the taller/common-block tree.
- Fixed scans for genuinely tiny security stores, subject to scan CPU cost.

Randomized partitioning is not in the set because the secure baseline was not
implemented. The four figures visualize regime minima, trusted-memory
crossover, privacy-valid modular/unified heterogeneity, and the medium-regime
cost/latency trade-off.

## 21. Baseline fairness audit summary

`BASELINE_FAIRNESS_AUDIT.md` records implementation fidelity and bias. The most
important qualifications are: packing is analytical; hybrid persistence is
undercharged; scans do not execute their full CPU/memory work; the random-remap
prototype is excluded; network profiles are synthetic; and all primary valid
rows retain the same one-host threat model. No general-purpose oblivious
relational engine was added because a faithful comparison was not modest in
scope.

## 22. Scientific caveats

- GAAP-derived means source-grounded semantics, not reproduction of GAAP.
- Record sizes, state counts, RTTs, bandwidths, stash size, and maps are
  experimental assumptions.
- The Path-ORAM implementation and analytical tree model are research
  simulators, not production ORAMs or security proofs.
- Python latency does not include cryptography, actual transferred bytes,
  persistence, queueing, contention, crash recovery, or a secure packed index.
- The Stage-5 classifier confirms only the frozen evaluated leakage channel.
- The PAuth-derived negative result bounds external validity.
- A sound partitioned design could change the frontier; this experiment cannot
  say which way.

## 23. Recommended architecture after Stage 5

Use `HYBRID-PH` when the trusted persistence mechanism can safely and
operationally hold permission plus history; switch to `HYBRID-P` as history
exceeds budget. When security state must remain outsourced, use the simplest
fixed modular schedule for heterogeneous records, or unpadded/securely packed
unified storage after workload-specific costing for homogeneous records. Treat
the schema compiler as maintainability/specification machinery unless a future
multi-action workload demonstrates real schedule reductions.

### Mandatory claim audit

| Question | Answer | Evidence |
| --- | --- | --- |
| Q1. Is canonical modular cheaper than unified in a meaningful regime? | **YES** | All S/M/L/H baseline regimes and all 48 heterogeneous record-size cases |
| Q2. Is unified cheaper in a meaningful regime? | **YES** | Equal-record GAAP control: 312 vs 368 blocks |
| Q3. Does naive fixed match canonical privacy? | **YES** | Both AUC 0.500 under random/grouped splits |
| Q4. Does canonical save over naive fixed? | **NO** | Identical schedule and analytical cost |
| Q5. Can randomized partitioning eliminate semantic-store leakage? | **NOT IMPLEMENTED** | Functional remap lacks sound eviction/cache machinery |
| Q6. If yes, does partitioning outperform unified? | **NOT APPLICABLE** | Q5 not implemented securely |
| Q7. Can PermissionDB fit trusted memory meaningfully? | **YES** | 16 KiB–2 MiB raw across regimes; budget-dependent |
| Q8. Can PermissionDB + history fit meaningfully? | **YES** | Fits S/M/H at 4 MiB and L at 64 MiB; persistence costs remain unmodeled |
| Q9. Does fixed scanning beat ORAM? | **CONFIGURATION DEPENDENT** | Wins only below size/profile crossovers |
| Q10. Is block-count-only comparison misleading? | **YES** | Actual blocks differ in bytes by store; packing changes results |
| Q11. Does record-size heterogeneity materially favor modular? | **YES** | 48/48 Stage-5 combinations favor canonical over packed unified |
| Q12. Does history growth change the preferred architecture? | **YES** | 16-MiB choice changes HYBRID-PH to HYBRID-P at 65,536 records |
| Q13. Does privacy-safe parallelism materially favor modular? | **YES** | Up to 5 ms saved in the REMOTE profile; strongest for hybrids |
| Q14. Is any architecture globally dominant? | **NO** | Memory, bytes, persistence, and workload crossovers conflict |
| Q15. Pareto-optimal set? | **HYBRID-PH, HYBRID-P, naive/canonical tie, unified unpadded/packed, and fixed scan for tiny stores** | Partition excluded pending a sound implementation |

**Is the current architecture contribution justified? ONLY AS A PARETO DESIGN
POINT. Should the empirical trade-off now be frozen? YES.**
