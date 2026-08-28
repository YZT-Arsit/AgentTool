# Stage-5 Trade-off Assumptions

This file freezes the analytical assumptions used by `src/stage5.py`. They are
experimental parameters, not measurements or claims about a GAAP deployment.

## Workload and state

The primary workload is the Stage-4 GAAP-derived `SEND_MESSAGE` case. Its
persistent state is limited to `PRIVATE_DATA_DB`, `PERMISSION_DB`, and
`DISCLOSURE_LOG`. The protected schedule has one private-data read, one
permission read, one history read, and one history write. The unprotected
reference naturally selects either a data or prior-history source, followed by
permission and history-update accesses.

The four record-count regimes are:

| Regime | Private data | Permissions | History |
| --- | ---: | ---: | ---: |
| S | 256 | 128 | 256 |
| M | 8,192 | 1,024 | 4,096 |
| L | 65,536 | 16,384 | 131,072 |
| H | 65,536 | 512 | 8,192 |

The baseline experimental record sizes are 4,096 B, 128 B, and 256 B,
respectively. Sweeps use data records of 512/1,024/4,096/16,384 B, permission
records of 64/128/256/512 B, and history records of 64/256/1,024 B.

## ORAM accounting

- Bucket size `Z=4`; logical capacity and block sizes are public.
- A tree with `N` logical blocks has height `ceil(log2(max(2,N)))`.
- One modeled Path-ORAM access transfers a complete root-to-leaf path in both
  directions: `2 * (height + 1) * Z` bucket blocks.
- Modular stores deterministically round each record size to its next power of
  two and choose block sizes independently.
- `physical_blocks` counts bucket blocks of the architecture's actual block
  size. `physical_blocks_4k_equiv` is transferred bytes divided by 4 KiB.
- Server storage allocates all buckets in a complete binary tree. Storage
  amplification divides this by logical payload bytes.
- The position-map proxy is 4 B per outsourced logical block. The stash proxy
  is six maximum-sized blocks. These are comparable accounting proxies, not
  measured Path-ORAM failure bounds.
- Canonical schedule metadata is 256 B. Other interpreter/code memory and
  cryptographic keys are omitted uniformly.

## Unified packing

`UNIFIED-FIXED` uses the largest modular block size. `UNIFIED-PACKED` is a
conservative analytical page model with 4-KiB pages and 16 B of per-record
packing metadata. Packing factor is `floor(4096/(record_size+16))`, at least one;
large data records span `ceil(record_size/4096)` pages. The access reveals a
page but not a slot. Full-path read/write transfer already covers the modeled
read-modify-write operation. The code does not implement encrypted slot
selection, concurrency control, or a production secure packing index.

## Hybrid and scan accounting

`HYBRID-P` charges the raw permission payload to trusted memory. `HYBRID-PH`
charges permission plus history payload. Both also include outsourced position
maps and the stash proxy. Persistence sealing, rollback protection,
checkpointing, recovery traffic, and freshness metadata are excluded and must
be added before deployment conclusions.

Fixed scans transfer the entire selected store per scan; a history update
transfers two complete scans. Scan CPU/cache cost is not measured, so scan
crossovers are bandwidth/round/ORAM-compute what-if estimates, not end-to-end
scan measurements.

## Read/write and latency assumptions

The read-heavy, balanced, and write-heavier vectors are `(data, permission,
history-read, history-write)` = `(1,1,.2,.25)`, `(1,1,.5,1)`, and `(1,1,1,2)`.
Path transfer is the same for reads and writes; the analytical local-compute
proxy adds a 15% uplift proportional to history writes. This is a sensitivity
model, not a measured storage engine.

Measured latency is Python mediator/trace-simulator time over 4,000 episodes and
three seeds. It does not transfer the analytical byte volume and must not be
treated as deployment latency. The what-if profiles are:

| Profile | RTT | Bandwidth |
| --- | ---: | ---: |
| LOCAL | 0.005 ms | 10,000 Mb/s |
| DATACENTER | 0.2 ms | 2,000 Mb/s |
| REMOTE | 5 ms | 200 Mb/s |

Modeled service time is `fixed rounds * RTT + bytes/(Mb/s * 125 B/ms) + local
compute`. Parallel schedules are fixed by public schema; no hidden-state-
dependent parallelism is used.

## Randomized-partition boundary

The functional remapping prototype reads an old partition slot and writes a new
random slot. It omits a formal client cache, oblivious/background eviction, and
a security proof. Exposing the write destination can link a later read without
those mechanisms. It is therefore `NOT IMPLEMENTED` as a privacy-sufficient
Partition ORAM. Its cost rows are excluded lower-bound engineering estimates,
not evidence about a sound partitioned design.
