# V12 final platform requirements

## Decision boundary

The historical 10/20/25 ms qualifications remain negative evidence. A larger
period on the same uncontrolled container is not a scheduler repair. A future
`STRICT_HARD_DEADLINE_PROFILE` campaign may start only after a materially
stronger execution platform is identified and frozen before any profile
candidate is tested.

## Required platform contract for hard deadlines

The platform freeze must establish all of the following, rather than infer them
from successful CPU affinity:

1. **Exclusive execution boundary.** Bare metal, or dedicated vCPUs backed by a
   documented hypervisor scheduling guarantee. The operator must control, or
   explicitly bound, steal time and host pauses.
2. **Exclusive pacer CPU.** The pacer CPU is owned through an exclusive cpuset;
   all Agent/framework/provider work and unrelated services are excluded.
3. **Kernel isolation.** The frozen boot configuration identifies the pacer CPU
   through `isolcpus` (preferably managed-IRQ aware), `nohz_full`, and
   `rcu_nocbs`, or documents an equivalent audited mechanism.
4. **IRQ isolation.** Default and per-IRQ affinity exclude the pacer CPU. The
   audit must include managed IRQs and prove that no device IRQ is pinned to it.
5. **No CPU quota throttling.** The execution cgroup has no CPU quota and its
   frozen policy cannot throttle the pacer. Pressure/throttle telemetry remains
   part of every qualification result.
6. **Deterministic CPU policy.** A fixed performance-oriented frequency policy
   and relevant power-management configuration are recorded. Frequency changes
   must not be silently delegated to an uncontrolled host policy.
7. **Pacer runtime.** The frozen implementation retains
   `runtime.LockOSThread` and absolute `CLOCK_MONOTONIC` `TIMER_ABSTIME`
   deadlines. A previous wake delay never shifts later public deadlines.
8. **Real-time scheduling.** If `SCHED_FIFO` or `SCHED_RR` is used, the exact
   priority, RT runtime limit, `CAP_SYS_NICE` authority, watchdog, and starvation
   controls are frozen. Merely exposing the policy names is insufficient.
9. **Memory readiness.** Memory-lock limits/capabilities, pre-faulting policy,
   GC policy, and allocation behavior on the pacer path are frozen and tested.
10. **No competing work.** A preflight and continuous audit prove no competing
    runnable task is admitted to the pacer CPU.
11. **Reproducible provenance.** OS, kernel, CPU model, virtualization status,
    cpuset/IRQ/cgroup policies, pacer source and executable hashes, and runtime
    version are bound in one immutable environment manifest.

## Acceptance rule

All hard-deadline platform capabilities must be mechanically verified before
new periods are declared. Candidate periods, denominators, workload order, and
the smallest-pass rule are then frozen before execution. No candidate period is
recommended or executed by this review.

The currently authorized container fails the exclusive-platform, kernel/IRQ
isolation, quota, real-time authority, and no-competing-work requirements.
Consequently it is not eligible for another strict-cadence qualification.

