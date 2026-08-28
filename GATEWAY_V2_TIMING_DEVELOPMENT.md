# CommonActionGateway V2 Timing Development

## Scope

This report covers development stress only. It does not output `TIMING_GO`,
`TIMING_CONDITIONAL_GO`, or `TIMING_NO_GO`. The prior V1 `TIMING_NO_GO` remains the only frozen
timing decision.

Four V2 development directories are preserved. `development_stress_windows`,
`development_stress_windows_final`, and `development_stress_windows_frozen` are calibration
artifacts produced before the last API/invariant cleanup. The reportable frozen-source
development artifact is:

`results_gateway_v2/development_stress_windows_frozen_source/`

Host-visible trace SHA-256:
`68EC606D57131F740869E6F47DE90F257F89D5D2B0C212149A1F92B2E95E1C0D`.

## Public development profile

| Parameter | Value |
|---|---:|
| Frame width `B` | 1,024 bytes |
| Sessions | 15 |
| Slots/session `H` | 120 |
| Request cadence | 10 ms |
| Response cadence | 10 ms |
| Preparation mask `delta_mask` | 5 ms |
| Start delay | 500 ms |
| Inter-session gap | 20 ms |

The workload used three sessions each for FAST, MEDIUM, SLOW, VERY_SLOW, and JITTERED. Each
session submitted 50 real HTTP Tool operations and 70 NOOP requests. Providers were distinct
loopback HTTP processes with service ranges 2--5, 20--40, 80--140, 300--500, and 2--500 ms,
respectively. Each provider also generated background CPU work on the Worker CPU. In total:

- 1,800 fixed request frames and 1,800 fixed response frames;
- 750 real Tool effects;
- 1,050 NOOP/cover slots;
- zero dummy heavy operations;
- zero result-ring full waits.

## Isolation configuration

This host is Windows. `SetProcessAffinityMask` placed the Pacer on CPU 0, the Worker/providers on
CPU 1, and the Cloud client on CPU 2. The status artifact confirms affinity applied. SCHED_FIFO,
CLOCK_MONOTONIC absolute `clock_nanosleep`, PREEMPT_RT, and isolated Linux CPUs were not active.
Consequently these measurements validate functional process isolation, not the Linux reference
timing claim.

## Mask selection and preparation

The 5 ms mask was selected before this frozen development run from the 10 ms public cadence and
the requirement to keep queue snapshot/AEAD outside transmit time; no V1 confirmatory label was
used. Frozen-source preparation lag was:

- p50: 0.408 ms;
- p95: 0.967 ms;
- p99: 1.235 ms;
- maximum: 2.089 ms.

All preparation completed before its public send deadline, leaving at least 2.911 ms observed
mask headroom. This is a development bound on one host, not a production worst-case bound.

## Release measurements

Global distributions:

| Boundary | p50 | p95 | p99 | max | mean |
|---|---:|---:|---:|---:|---:|
| Cloud request release slip | 0.439 ms | 0.972 ms | 1.274 ms | 5.957 ms | 0.483 ms |
| Gateway response release slip | 0.438 ms | 0.970 ms | 1.254 ms | 1.482 ms | 0.477 ms |
| Cloud receiver response lag from public deadline | 0.439 ms | 0.972 ms | 1.274 ms | 5.957 ms | 0.483 ms |

Response release by private workload:

| Class | Mean | p95 | p99 | Max | Slots |
|---|---:|---:|---:|---:|---:|
| FAST | 0.462 ms | 0.955 ms | 1.244 ms | 1.461 ms | 360 |
| MEDIUM | 0.472 ms | 0.943 ms | 1.130 ms | 1.314 ms | 360 |
| SLOW | 0.498 ms | 0.959 ms | 1.228 ms | 1.464 ms | 360 |
| VERY_SLOW | 0.465 ms | 0.976 ms | 1.262 ms | 1.358 ms | 360 |
| JITTERED | 0.485 ms | 0.991 ms | 1.408 ms | 1.482 ms | 360 |

A group-level permutation test on per-session mean slip gives p=0.211 with 2,000 permutations.
Unlike V1 development, no class exhibits multi-hundred-millisecond scheduler stalls. This is a
useful causal result but not an equivalence/privacy test and not confirmatory evidence.

The 5.957 ms Cloud-side/receiver maximum did not occur at the Gateway response-send boundary,
whose maximum was 1.482 ms. It is retained as evidence that application/socket and receiver
timing are not packet-level guarantees even after the Pacer process is separated.

## Development conclusion

The separate process/core design removes the obvious V1 contention path on this workload. It is
ready for Linux reference-platform engineering, not for a timing claim. Before a fresh holdout:

1. run the identical source on Linux with verified Pacer/Worker CPU separation;
2. record whether SCHED_FIFO was applied or explicitly unavailable;
3. predeclare an equivalence margin from Linux calibration, not V1 holdout labels;
4. freeze code, kernel/CPU configuration, mask, cadence, frame size, attacks, and aggregation;
5. generate a wholly new confirmatory dataset.

No confirmatory experiment was run in this implementation stage.

## 2026-08-28 Linux allocation check

The canonical continuation did **not** authorize a timing freeze or holdout on
the available Linux allocation. It is a Docker/cgroup-v2 environment with a
25-CPU quota, recorded cgroup throttling, no permitted `SCHED_FIFO`, and no proof
of dedicated physical cores. Functional affinity calls succeed, but that is not
the reference-platform isolation required by the frozen procedure.

One development-only launch was attempted and preserved at
`results_gateway_v2/development_stress_linux_20260827/`. It stopped before any
statistical timing analysis with `incomplete V2 socket-boundary trace`. The
legacy `gateway_v2` cloud receiver decoded the response header using a stale
layout: its observed session value was `197120` and its slots were `0..14`, so
receiver timestamps could not be joined to the 1,800 valid public slots. This
is a legacy-client parse defect, not evidence for or against timing privacy.
The failed artifact is preserved; it was not repaired and rerun merely to
obtain a timing number on an unsuitable host.

Consequently no `TIMING_V2_FREEZE_MANIFEST.json`, fresh holdout, or timing
privacy result exists. The current status remains `NOT_TESTED / OPEN`.
