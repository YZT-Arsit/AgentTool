# Remote Linux environment audit

## Provenance and synchronization

The current local worktree was synchronized to the authorized host before canonical source changes in this phase.

- Local repository HEAD: `b08c044a05b4ed020962d234db91e8912a5d1ed7`
- Local worktree: dirty by design; the uncommitted permanent IR-v1 freeze/Pareto artifacts were included.
- Tracked diff at synchronization: 4 files, 51 insertions, 10 deletions, plus the untracked IR-v1 audit artifacts listed by `git status --short`.
- Submodule command: not usable because `.gitmodules` has no mapping for the historical `external_pir/simplepir` gitlink.
- Transfer archive: `agenttool_current_20260827.tar.gz`, 19,703,238 bytes, SHA-256 `3D13C3A4A1A672E46888EEA70ACE8293DD096D9A0DB7087FB0016784D00CE744`.
- Remote worktree: `/root/autodl-tmp/mediation_trace_validation`.
- Excluded from transfer: credentials, `.git`, virtual environments, toolchains, pytest caches, compiled Windows binaries, the 943 MB Stage-12 external benchmark checkout, and the two largest historical generated-result trees. These are exclusions from the remote working copy, not deletions from the local repository.

All six frozen IR-v1 evidence files were hashed after extraction on Linux and exactly matched `IR_V1_BASELINE_MANIFEST.json`.

## Operating environment

| Item | Observed value |
| --- | --- |
| Guest OS | Ubuntu 22.04.5 LTS |
| Kernel | `5.15.0-94-generic` |
| Virtualization | Docker/container (`systemd-detect-virt=docker`, overlay root filesystem) |
| Host CPU topology exposed | 2 × Intel Xeon Platinum 8470Q sockets, 52 cores/socket, SMT2, 208 logical CPUs |
| Container CPU quota | `2500000/100000` = 25 CPU-equivalents; `nproc=25` |
| cpuset | CPUs `0-207` are visible/effective despite the quota |
| NUMA | 2 nodes |
| GPU | NVIDIA GeForce RTX 5090, 32,607 MiB |
| Driver / advertised CUDA | 580.76.05 / CUDA 13.0 |
| CUDA compiler | `nvcc` not installed |
| Python | 3.12.3 |
| Go | not installed at audit time |
| cgroup memory limit | 96,636,764,160 bytes (90 GiB) |
| Host memory visible through `/proc` | approximately 754 GiB; not the container limit |
| Data filesystem | 50 GiB XFS at `/root/autodl-tmp` |
| Root filesystem | 30 GiB overlay |

The AutoDL login banner's “25 cores / 90 GB” description agrees with the cgroup quota and memory limit, not with the full topology and host-memory values exposed by `lscpu` and `/proc`.

## Timing capabilities

- `taskset` and `sched_setaffinity` work.
- Physical SMT topology is visible (for example, CPU 0 and CPU 104 are siblings).
- `CLOCK_MONOTONIC` is available through `clock_gettime`, reports nanosecond resolution, and is monotonic/non-adjustable.
- `SCHED_FIFO` is known to the kernel, but an actual `chrt -f 1` smoke test failed with `Operation not permitted`.
- The container can choose affinities but cannot reserve physical cores from unrelated host tenants, and its global CPU quota may introduce throttling across otherwise distinct affinities.
- PREEMPT_RT was not established; the kernel identifies as ordinary Ubuntu SMP.

## Platform classification

**Shared cloud container; not yet a timing reference platform.**

Linux functional/E2E tests and timing development calibration are appropriate. A confirmatory timing freeze is permitted only if development measurements show stable isolation despite cgroup quota and shared-host scheduling. Failure to obtain reproducible isolation must be reported as `TIMING_PRIVACY=NOT_TESTED/OPEN`, not repaired statistically.

## Raw evidence

`REMOTE_ENV_RAW.txt` preserves the command output without credentials. It includes `uname`, OS release, full `lscpu` and `lscpu -e`, topology files, GPU state, Python/Go availability, memory/filesystem/cgroup state, affinity checks, realtime-scheduler failure, and monotonic-clock information.
