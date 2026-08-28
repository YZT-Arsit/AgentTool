# CommonActionGateway V2 Security Matrix

The matrix distinguishes implemented invariants from development evidence and confirmatory
privacy. No row authorizes a timing-go decision.

| Property | Status | Evidence / boundary |
|---|---|---|
| `NOMINAL_FIXED_SCHEDULE` | PASS | Public profile generates exactly `H` request/response deadlines independent of completion; FAST/SLOW continuation test passed |
| `ACTUAL_RELEASE_TIMING` | DEVELOPMENT_ONLY | Frozen Windows Gateway-send stress: p99 1.254 ms, max 1.482 ms, grouped p=0.211; not Linux and not a fresh equivalence holdout |
| `FIXED_SIZE` | PASS | Every public request and response is exactly 1,024 bytes; RESULT/WAIT share one AEAD path |
| `FIXED_DESTINATION` | PASS | One persistent `CommonActionGatewayV2` TCP tunnel; Cloud has no provider socket |
| `RESULT_RELEASE_DECOUPLING` | PASS | Completion publishes only to result ring; Pacer polls once at public cutoff; no wake/signal/socket access from Worker |
| `CONTINUATION_INDEPENDENCE` | PASS | Pre-journal FAST/SLOW delivered in slots 2/8; durable journaling moved current Windows development delivery to 4/10. Both retain the same 12-slot public session and continue cover afterward. |
| `DUMMY_HEAVY_OPS_ZERO` | PASS | Frozen stress: 1,050 NOOP slots and zero dummy Tool/LLM work |
| `PROVIDER_REAL_IO` | PASS | Worker used five separate local HTTP emulator processes; no in-Gateway latency sleep |
| `PROCESS_ISOLATION` | PASS_FUNCTIONAL | Distinct PIDs and Windows affinity applied; Linux SCHED_FIFO/isolation still untested |
| `CRITICAL_PATH_ALLOCATION` | PASS_APPLICATION_PREP | Fixed AEAD preparation reports zero Go allocations/call; kernel/TCP allocation is outside this assertion |
| `FAILURE_SHAPE` | IMPLEMENTED_NOT_STRESS_VALIDATED | Error/timeout/cancel map to fixed result records and cannot change profile; systematic failure stress remains pending |
| `EFFECT_RECOVERY` | PASS_LOCAL_WITH_PROVIDER_CONSTRAINT | Durable prepare/commit journal and restart tests pass. READ_ONLY and declared IDEMPOTENT_EFFECT may retry; ambiguous NON_IDEMPOTENT_EFFECT fails closed for reconciliation. Exactly-once is not claimed without provider support. |
| `PACKET_LEVEL_TIMING` | OPEN | TCP socket timestamps only; TCP control traffic is unshaped; SO_TXTIME/ETF timed datagram is not implemented |
| `RESOURCE_PRIVACY` | OPEN | Process/core separation reduces one interference path but does not hide host-wide CPU/cache/memory telemetry |
| `WINDOWS_TIMING_PRIVACY` | NOT_CLAIMED | Windows is a functional fallback and cannot establish timing closure |
| `LINUX_TIMING_PRIVACY` | NOT_TESTED | Linux packages cross-build, but reference runtime and fresh holdout are pending |
| `CONFIRMATORY_TOOL_FREQUENCY_PRIVACY` | NOT_TESTED | The old V1 AUC 0.6525/0.6594 failure is preserved; V2 requires a new untouched holdout |

Current V2 state: implementation and development engineering complete; confirmatory timing
security deliberately unresolved.
