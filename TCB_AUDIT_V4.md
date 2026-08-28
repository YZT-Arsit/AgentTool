# Runtime TCB audit V4

## Claim boundary

The full OpenAI Agents SDK and Microsoft Agent Framework are **not** trusted at
runtime. They are source/compiler inputs and evaluation dependencies. The LLM,
specialist workers, and Agent execution server remain one honest-but-curious
untrusted compute plane. The trusted enforcement substrate is the bounded
control representation/interpreter, Privacy Kernel, private lookup client role,
and the Gateway mechanisms that enforce encrypted common-endpoint framing,
pacing, provider mediation, and effect recovery.

This is a small control substrate relative to either complete Agent framework,
but it is not a “few hundred lines” TCB: the Gateway is material.

| Code group | Files | Physical LoC | Approx. code LoC | Runtime TCB? |
| --- | ---: | ---: | ---: | --- |
| Trusted control substrate | 7 | 1,160 | 976 | Yes |
| Trusted Gateway enforcement | 15 | 1,745 | 1,603 | Yes |
| **Project runtime TCB total** | **22** | **2,905** | **2,579** | **Yes** |
| Compiler | 3 | 296 | 259 | No; trusted build input validation remains required |
| Corpus/extraction tooling | 5 | 1,188 | 1,065 | No |
| Provider emulator | 2 | 179 | 168 | No |
| Experimental runners/analysis | 6 | 1,278 | 1,122 | No |
| Untrusted Cloud plane adapters | 3 | 340 | 308 | No |

Exact per-file counts are in `TCB_INVENTORY_V4.csv`. Tests, historical stages,
figures, reports, and upstream framework sources are excluded from these groups.

## Runtime dependencies

- Python standard library and `cryptography`/AES-GCM native backend.
- Go standard library networking, HTTP, JSON, AES-GCM, file, mmap, syscall, and
  monotonic-clock facilities.
- Pinned official SimplePIR client/server primitive at commit
  `e9020b03bf2872c75b8954e749e32408b5db87ed`; its upstream implementation is a
  separately trusted cryptographic dependency, not counted as project LoC.
- OS isolation, file durability/rename, permissions, process scheduling,
  shared-memory, and socket semantics.

## New durable state

The Gateway Worker now persists a trusted operation journal before provider
dispatch. It records only trusted-side operation IDs, declared effect semantics,
state, and bounded results. `READ_ONLY` and `IDEMPOTENT_EFFECT` operations can be
retried under their stated contracts. `NON_IDEMPOTENT_EFFECT` operations found
prepared or ambiguous after restart fail closed as
`AMBIGUOUS_EFFECT_RECONCILIATION_REQUIRED`; the system does not claim exactly
once without a provider idempotency/reconciliation contract.

## Remaining TCB gaps

- The journal is a correct local copy-on-write/fsync prototype, not a replicated
  or malicious-storage-resilient transaction log.
- Compiler output validation and capsule authentication are not yet a complete
  secure build pipeline.
- PIR client/server roles remain integrated in the local bridge experiment.
- Timing, resource, microarchitectural, GPU, and performance-counter channels
  are not closed by this audit.
- The long-horizon E2E run was blocked by local Application Control, so this TCB
  inventory must not be read as a completed system-level privacy validation.
