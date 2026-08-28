# CommonActionGateway V2 Implementation Audit

## Audit result

V2 implements the required process split and fixed public session semantics. This is an
implementation/development audit, not a timing-privacy decision. The preserved V1 result remains
`TIMING_NO_GO`.

## Components

| Component | Source | Process responsibility |
|---|---|---|
| Protocol and fixed records | `common_action_gateway_v2/protocol.go` | Fixed request/result formats and equal-width AES-GCM request/response frames |
| Public profile | `common_action_gateway_v2/profile.go` | `B`, request/response cadence, `H`, mask, and public session span |
| Shared rings | `common_action_gateway_v2/ring.go`, `mapping_windows.go`, `mapping_linux.go` | Bounded memory-mapped SPSC request and result queues |
| Gateway Worker | `common_action_gateway_v2/worker.go`, `cmd/gateway-worker` | Request decryption, NOOP rejection, provider execution, idempotency, result publication |
| Provider adapters | `common_action_gateway_v2/provider.go` | Persistent real HTTP I/O; non-loopback generic HTTP disabled unless explicit |
| Local providers | `common_action_gateway_v2/provider_emulator.go`, `cmd/local-provider-emulator` | Separate real HTTP services with local service-time/CPU distributions |
| Gateway Pacer | `common_action_gateway_v2/pacer.go`, `cmd/gateway-pacer` | Sole public socket owner, independent public clock, cutoff snapshot, AEAD preparation, send |
| Cloud request pacer | `common_action_gateway_v2/client.go`, `cmd/gateway-cloud-client` | Prebuilt fixed encrypted request/NOOP frames and independent request clock |
| Platform timing/isolation | `platform_linux.go`, `platform_windows.go` | Linux absolute monotonic sleep/affinity/SCHED_FIFO; Windows functional fallback |
| Transport boundary | `transport.go` | Persistent fixed-frame TCP backend and explicit unimplemented timed-datagram capability |
| Local orchestration | `gateway_v2/runner.py` | Starts distinct processes and merges only host-visible socket timestamps |
| Development analysis | `gateway_v2/development.py` | Label-conditioned slip and group-level permutation analysis |

## Process and endpoint evidence

The frozen development run used distinct PIDs:

- Worker: 10460;
- Pacer: 28228;
- Cloud client: 32972;
- providers: 3640, 7124, 33084, 2544, and 25916.

Only the Pacer imports/owns the Agent-Cloud `net.Conn`. Worker source contains no `net.Conn` and
cannot call `WriteFixedFrame`. All five providers are loopback HTTP servers reached by the Worker;
the Cloud trace contains only destination `CommonActionGatewayV2`.

## Why completion cannot directly send

The Worker completion path is:

```text
ProviderAdapter.Execute
  -> fixed ResultRecord
  -> Worker-internal completion channel
  -> single result-ring writer
  -> atomic publish to shared-memory ring
```

There is no Pacer handle, socket descriptor, callback, condition variable, eventfd, or signal in
that path. The Pacer performs one `TryPop` only after its public cutoff timer expires. The result
ring is polled; Worker publication does not wake it.

The Pacer validates at setup that the request ring can hold the entire public epoch. Its request
reader performs one nonblocking publish per public fixed request and cannot enter a
Worker-progress-dependent retry loop.

## Critical path audit

Before the public epoch, the Pacer preallocates all response frames and generates all AEAD nonces.
At `Tk-delta_mask` it:

1. performs at most one fixed ring read;
2. copies a fixed result or zero WAIT record;
3. runs the same fixed-size AEAD preparation;
4. records the prepared timestamp in memory.

At `Tk` it performs absolute wait, fixed `net.Conn.Write`, and one assignment into a preallocated
timing ring. Operation-ID string conversion and JSON encoding occur only after all slots finish.
The Go allocation test reports zero allocations per `ResponseFrameBuilder.Prepare` call.

The TCP runtime/kernel may still allocate or block internally; V2 does not equate application
zero-allocation with packet-level determinism.

## Session and continuation proof

The connection is established once and remains active for all public sessions. Session bases and
all slots are derived only from `PublicProfile`. Neither the Worker nor result ring can alter
`Slots`, cadence, gap, or connection teardown.

The pre-journal continuation integration test produced:

- FAST result delivered by public slot 2;
- SLOW result delivered by public slot 8;
- exactly 12 response slots for each;
- identical 50 ms nominal response deltas, 1,024-byte frames, destination, and public lifetime;
- scheduled frames continued after both results;
- two real effects and zero dummy heavy operations.

After durable journal hardening, local Windows development observed delivery in
slots 4 and 10 respectively. This latency increase is preserved; the current
invariant is that both results use already-scheduled slots, the fast completion
precedes the slow completion, and neither extends the 12-slot session. It is not
a timing-privacy result.

If a result is not present at a cutoff, WAIT is sent and the result remains private until another
already-existing slot. A result after `H` cannot extend the tunnel and is fail-closed/undelivered.

## Provider and failure semantics

The Worker performs real HTTP request/response I/O. Local tests configure only loopback URLs.
Non-loopback endpoints require `allow_generic_http=true` and are disabled in all V2 runs.
Success, provider error, timeout, cancellation, and ambiguous non-idempotent state map into one
fixed `ResultRecord`; they do not alter public scheduling. Providers declare `READ_ONLY`,
`IDEMPOTENT_EFFECT`, or `NON_IDEMPOTENT_EFFECT`. The Worker durably prepares an operation before
dispatch and commits its bounded result afterward. A restarted non-idempotent operation in an
uncertain state is not retried and returns reconciliation-required status; exactly-once is not
claimed without provider support. Unit tests cover crash after prepare, retry after restart for an
idempotent provider, durable committed-result recovery, and ambiguous failure.

## Build and test status

- Windows Go tests and all command builds: PASS.
- Linux command/package cross-build: PASS.
- Linux test execution: NOT RUN on this Windows host.
- Python process/invariant/continuation tests: PASS.
- Current focused Python validation: 26 passed, 1 deselected.
- Current broad Python run: 163 passed, 1 skipped, and one environment setup error; the affected
  case reran with a repository-local temporary directory and then skipped because Windows
  Application Control blocked the local Pacer executable.
- V1 files and `results_timing_closure/confirmatory_final_*`: unchanged.

## Remaining implementation limitations

- Windows uses `SetProcessAffinityMask` but is not a reference timing platform.
- `SCHED_FIFO` success and isolated-CPU behavior have not been exercised on Linux.
- TCP control traffic and kernel packet release are not shaped.
- `SO_TXTIME`/ETF is represented only as an explicitly unimplemented future timed-datagram
  capability; using it correctly needs Linux qdisc/capability setup and non-TCP framing.
- Resource/microarchitectural isolation is not established.
- The memory-mapped rings are volatile experimental IPC, not durable production queues. The
  effect journal is durable local state, but is neither replicated nor malicious-storage robust.
