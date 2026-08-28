# Timing Design Specification

## Frozen boundary

The Agent Cloud is untrusted and can observe its PIR server, common executor, and all metadata on its persistent
connection to `CommonActionGateway`. The Gateway and downstream providers are trusted/outside this adversary.
Provider GPU/VRAM/kernel/resource telemetry is not in the Agent-Cloud view. Session start and the selected public
profile are public.

## Public schedules

| Profile | Purpose | Slots | Cadence | Response lag | Frame |
|---|---|---:|---:|---:|---:|
| `STANDARD` | one action/result episode | 24 | 50 ms | 25 ms | 1,024 B each direction |
| `LONG_SEQUENCE` | 100-operation Tool sequence + drain | 200 | 10 ms | 5 ms | 1,024 B each direction |
| `VERY_SLOW_VALIDATION` | 1.5–3 s provider matrix | 64 | 50 ms | 25 ms | 1,024 B each direction |
| `PIR` | selection/control lookup | 100 | 5 ms | N/A | fixed SimplePIR query/answer shape |

These constants were written to `results_timing_closure/frozen_public_profiles.json` before the final holdout.
They are not Agent-, Tool-, provider-, or label-specific.

## Native persistent action channel

Two native processes communicate over one pre-established full-duplex TCP connection:

```text
Privacy/control encoder -> encrypted private outbound frames
                         -> native cloud request pacer
                         -> persistent TCP socket
                         -> CommonActionGateway receiver
                         -> async real provider worker -> private result queue
                         -> native Gateway response pacer
                         -> same persistent TCP socket
                         -> cloud receiver
```

The client process owns request deadlines; the Gateway process owns response deadlines. Neither send loop runs in
the secret-dependent Agent path. Frames use fresh AES-GCM nonces and a fixed width. The cloud sees only
`CommonActionGateway`, one request and one response per slot, and public episode/profile boundaries.

If a result is ready, one queued result is encrypted into the next response slot. Otherwise the Gateway emits WAIT.
NOOP does not create a result, provider call, effect, or heavy computation. Real result and WAIT are equal-width
ciphertexts. Provider completion never invokes `send`.

## PIR schedule

Every public PIR slot executes official SimplePIR `Query`, server matrix answer, and client recovery. Real lookups use
the required index; unused slots choose randomized rows 1000–1063 from a reserved dummy region. Dummy results are
verified and discarded before `AgentControlExecutor`. The native Go scheduling loop uses a monotonic/public deadline;
it is outside Agent logic, but this experiment records server-call timestamps rather than packet timestamps.

## Downstream latency matrix

Real asynchronous providers measured: FAST 13.7–19.8 ms, MEDIUM 121.1–194.5 ms, SLOW 718.3–854.0 ms,
VERY_SLOW 1,572.6–2,684.9 ms, and JITTERED 427.4–680.5 ms in the sampled development run. These completion times
enter a private queue and do not alter public slot count or nominal deadlines.

## Overflow and effects

The tested horizons cover the controlled providers. A future over-horizon result must follow a public fail-closed
policy; it may not extend only the slow secret case. Continuation-epoch count is not hidden by this prototype.
Every requested Tool effect executes once. Dummy heavy operations remain zero.

## Measurement level

`APPLICATION_TIMESTAMP`: private provider start/completion, trusted diagnostic only.  
`SOCKET_BOUNDARY_TIMESTAMP`: cloud send/receive and Gateway receive/send, primary evidence.  
`PACKET_TIMESTAMP`: not captured. `PktMon` is installed but system-wide capture could include unrelated traffic and
was not used; no packet-level privacy claim is made.
