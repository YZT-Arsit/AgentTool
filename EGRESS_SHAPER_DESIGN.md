# Egress shaper design

## Scope

This Stage-13 component is a reusable, finite paced-cover transport experiment. It is not a complete agent-trajectory privacy system. The experiment implements one persistent outbound channel; a deployed system would require persistent, secret-independent queued cover channels in both request and response directions.

## Trust boundary

The Privacy Kernel is the only trusted execution authority. The LLM, specialist workers, agent execution server, and their RPC host form one honest-but-curious compute plane. The protected transport view includes protocol-visible activation envelopes, sizes, release/arrival timing, burstiness, and public commit slots. CPU caches, microarchitecture, GPU telemetry, and performance counters are excluded.

## Processes and connection

- A runtime adapter submits trusted work readiness to a private shared mailbox.
- A dedicated sender process owns the public schedule and is pinned to a reserved logical CPU.
- A separate receiver process owns the attacker-visible receive timestamp and is pinned to another reserved logical CPU.
- A persistent, prewarmed loopback TCP connection uses `TCP_NODELAY`.
- The sender and receiver are separate processes, not threads. This repairs the observed Python-GIL starvation that previously bunched all arrivals after the epoch.

## Slot semantics

For public configuration `H=5`, runtime-specific public `Delta`, and `B=16384` bytes, slot `k` has deadline `t0 + k*Delta`. Each slot sends exactly one prebuilt `B`-byte envelope and performs three Path-ORAM trace accesses. Real/cover status is not serialized. A late proposal cannot move the deadline; it fails closed at the fixed pre-commit guard. No dummy envelope produces an external effect.

## Synchronization

The sender resets its per-epoch state, chooses `t0`, and acknowledges both values before the adapter proceeds. This removes a start/reset race. Commit eligibility is sampled once at a public guard point and copied to a separate one-bit gate consumed by the effect endpoint. A proposal arriving after the guard cannot be committed.

## Limitations

The envelope payload is an indistinguishability abstraction using fixed random bytes, not a production record protocol. Worker activation is protected only when it is carried through this channel. The current artifact has no response-direction shaper and does not prove end-to-end concealment of every worker/RPC activation in a real distributed agent deployment.
