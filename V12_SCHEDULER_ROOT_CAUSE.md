# V12 scheduler root-cause audit

The scheduler failure mechanism is established, but its lowest-level host trigger is not.

The base scheduler placed a Go goroutine around `time.Sleep` calls at independently computed slot cutoffs and deadlines. That preserves absolute deadline arithmetic, but the goroutine can still be delayed by Go runtime work, GC, OS scheduling, cgroup throttling, or host/hypervisor activity. Fresh pre-hardening falsification did not reproduce the historical 33 ms stall: schedule-only completed 500/500 (178,000 slots) and workload contention completed OpenAI 100/100 plus Microsoft 100/100 (71,200 slots), all without a miss.

The hardened Linux path uses `runtime.LockOSThread` and `clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)`. On the authorized host the framework/process CPU set was restricted to 0-206 and the pacer thread was pinned to CPU 207. The runner mechanically verified both. The host exposes no kernel-isolated CPU.

Despite that hardening, three decisive failures occurred:

- 10 ms: `DEV-SCHED-HARDENED-NOOP-0093`, slot 108, 10.727857 ms late.
- 20 ms: `DEV-SCHED-REQUAL2-P20-NOOP-0954`, slots 13 and 14, 42.823282 and 25.271952 ms late.
- 25 ms workload: `DEV-SCHED-P25-MS-REPEAT10-035`, slot 9, 29.056672 ms late.

All expired slots failed closed and were not transmitted. Later deadlines remained absolute; no catch-up burst or dynamic session extension was introduced.

The measured cgroup throttle counter did not change around these incidents. The 25 ms incident had no measured GC pause or nonvoluntary-context-switch delta in the incident window, and CPU PSI was zero. The 20 ms incident's measured GC pause delta was about 0.696 ms, far below the 42.8 ms stall. Provider execution is excluded as a general cause because the decisive 10 and 20 ms failures occurred in NOOP sessions.

Therefore the supported class is `PACER_OS_THREAD_DESCHEDULING_ON_NON_KERNEL_ISOLATED_CPU`. The exact host process, interrupt, hypervisor pause, or scheduler cause is not observable in this VM and remains `UNRESOLVED`. This is a reliability result, not timing-privacy evidence.

Private scheduler diagnostics do not enter OHTTP/BHTTP, Relay public events, the strict structural projection, or the size projection. The dedicated non-interference regression passed.

