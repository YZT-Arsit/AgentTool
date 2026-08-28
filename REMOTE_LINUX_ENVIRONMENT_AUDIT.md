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
| Go | 1.23.12 installed after the initial snapshot under `/root/autodl-tmp/toolchains/go` |
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
- A repeated `chrt -f 10 true` check also failed with `Operation not permitted`.
- `taskset -c 0 true` succeeded, but affinity is not exclusivity: the container may choose among all 208 host logical CPUs while sharing a 25-CPU cgroup quota.
- The observed cgroup `cpu.stat` already recorded throttling (`nr_throttled=6`, `throttled_usec=3200976`) during the audit window.
- The container can choose affinities but cannot reserve physical cores from unrelated host tenants, and its global CPU quota may introduce throttling across otherwise distinct affinities.
- PREEMPT_RT was not established; the kernel identifies as ordinary Ubuntu SMP.

## Platform classification

**Shared cloud container; not yet a timing reference platform.**

Linux functional/E2E tests and timing development calibration are appropriate. This allocation does not meet the predeclared reference condition because real-time scheduling cannot be applied and physical cores cannot be reserved from the host. Therefore a timing confirmatory freeze/holdout is **not authorized on this allocation**; timing remains `NOT_TESTED/OPEN` even if development calibration looks favorable.

## Toolchain and functional follow-up

After the environment snapshot, Go 1.23.12 for Linux/amd64 was installed under the task data disk solely for this experiment. The downloaded archive SHA-256 was `d3847fef834e9db11bf64e3fb34db9c04db14e068eeb064f49af747010454f90`; it matches the checksum published on the official Go downloads page. The remote Gateway module then passed `go test ./...`.

The updated local source was transferred in versioned archives rather than by resetting the remote checkout. The IR-v2 source archive SHA-256 was `0897A2B4344D4ADE3C1CFBAF6F52E716D1F61A7480B92E9B68FDB5431C473283`; the later E2E patch archive SHA-256 was `57C7AA11DDC5D399F38B14A9E40D0ADE62E072978E63AC672CAEB405A0E58BA8`. Neither archive contains credentials.

Linux functional follow-up completed:

- 19 focused IR-v2/canonical tests passed on the remote host after the private-state and partial Agent-as-Tool additions;
- the live canonical Gateway integration test passed;
- the native-Agent -> full-preprocessing SimplePIR -> kernel -> proxy -> Gateway -> local model/Tool -> kernel feedback execution returned successfully;
- separate read-only, effectful, and logical-handoff workflows all passed their exact heavy-operation/effect invariants.
- a real local Qwen2.5-0.5B-Instruct GPU provider completed one bounded model -> Tool -> model workflow through the canonical Gateway.

These are functional integration results, not timing-reference evidence. A Gateway diagnostic field that previously set `reference_timing_platform=true` solely for Linux was identified as incorrect and repaired; timing-reference status now requires both applied affinity and applied real-time scheduling. The shared container has not met that condition.

## Raw evidence

`REMOTE_ENV_RAW.txt` preserves the command output without credentials. It includes `uname`, OS release, full `lscpu` and `lscpu -e`, topology files, GPU state, Python/Go availability, memory/filesystem/cgroup state, affinity checks, realtime-scheduler failure, and monotonic-clock information.
