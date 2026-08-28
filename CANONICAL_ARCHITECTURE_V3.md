# Canonical Architecture V3

Status: **CANONICAL ACTIVE TARGET**. This document is the only architecture
composition guide for current implementation work. Historical Stage 1-13
documents are evidence records, not components to be combined into this design.

Current executable core: IR-v2 represents structured model decisions, Tool
identity/arguments/call IDs/results, private context reinsertion, bounded model
resume, final return, explicit failure states, and logical handoff. The live
Linux canonical adapter is deliberately narrower: it lowers one source-traceable
native Agent with exactly one Tool to `MODEL -> TOOL -> MODEL -> RETURN` and
rejects other shapes. Broader IR-v2 constructs must earn separate executable
support and must not be inferred from this adapter.

## System boundary

```text
Trusted Privacy Kernel
  private selection + SimplePIR client + capsule cache
  private Control Kernel + trusted encoder/result consumer
             |
             | fixed opaque request envelopes / opaque result envelopes
             v
Untrusted Cloud Slot Proxy U
  public profile + public session/slot clock + fixed-rate forwarding only
             |
             | one long-lived fixed-destination tunnel
             v
Trusted CommonActionGateway V2
  isolated Pacer process <-> fixed shared rings <-> Worker process
             |
             | trusted provider adapters and EffectGate
             v
Local model/read-only/effectful provider services
```

Agent selection is a real SimplePIR client operation inside the Privacy Kernel.
Logical Agent identity and control state are data consumed by one common
`AgentControlExecutor`; they are never process, queue, URL, or RPC identities.
`HANDOFF(j)` mutates the trusted logical Agent ID and may schedule a later PIR
lookup. It never activates an Agent-specific physical endpoint.

## Public schedules

The canonical base profile has three predeclared schedules:

- `Gamma_pir`: a fixed sequence of real SimplePIR queries. A pending capsule
  lookup queries its row; otherwise the trusted client queries a reserved dummy
  row with fresh randomness.
- `Gamma_control=(H_control, Delta_control, B_control)`: one public
  `CONTROL_SLOT` opportunity per tick. At most one private transition advances.
  Pending work holds state; early `RETURN` produces cover slots through the
  public horizon.
- `Gamma_io=(B_io, Delta_request, Delta_response, mask, session_policy)`: fixed
  request and response envelopes through one CommonActionGateway destination.

The canonical experimental lifetime policy is a long-lived tunnel spanning a
publicly configured number of task epochs. Tunnel creation, epoch count, and
closure are public configuration and do not depend on private completion.

## Control and heavy operations

The private Control Kernel supports `LLM`, `TOOL`, `HANDOFF`, `STATE_GET`,
`STATE_SET`, declarative `BRANCH`, `RETURN`, and `NOOP`. It owns the capsule
cache, logical Agent ID, control state, pending action/result, and per-session
state. It emits at most one trusted action descriptor per control tick.

LLM and Tool work remain shared heavy primitives behind the Gateway. NOOP and
cover control/PIR slots never execute heavy work. Effectful tools pass an
`EffectGate`: authorization and the private descriptor are prepared before a
single idempotent operation-ID-bound release. Provider capabilities determine
whether ambiguous post-request timeouts can be reconciled; unsupported
exactly-once guarantees are reported rather than inferred.

## Cryptographic envelopes

The trusted encoder creates fixed-size AEAD envelopes before they enter U. The
public authenticated header is:

```text
protocol_version || direction || public_session || public_slot || public_profile_id
```

U has no encryption key and cannot parse an opcode, provider, Tool identity,
operation ID, payload, result, Agent ID, registry index, or capsule. The trusted
Gateway decrypts requests; the Privacy Kernel decrypts responses. Replay,
session, profile, direction, duplicate, and monotonic-slot checks are mandatory.

## Private persistent state

The base profile uses trusted/local encrypted state. Retained Path ORAM code is
an `OPTIONAL_PRIVATE_STATE_BACKEND` only. It is not an Agent-selection,
activation, dispatch, Tool-destination, or Gateway mechanism.

## Local-only integration profile

Automated execution uses pinned local framework checkouts, the pinned official
SimplePIR source, loopback HTTP model/Tool providers, and local generated
workloads. OpenAI-compatible and generic HTTP adapters are optional and disabled
by default. No external provider is contacted by canonical tests.

## Phase-0 audit

Completed 2026-08-27 before new experiments. Source inventory confirmed:

1. Gateway V2 already has separate Worker/Pacer processes, shared rings, fixed
   frames, persistent transport, and local HTTP providers.
2. `gateway-cloud-client` currently violates the intended trust boundary by
   loading `PrivateWorkload` and holding the AEAD key. It is superseded as a
   canonical client and will become an opaque forwarding proxy.
3. The official SimplePIR bridge exists and has prior standalone correctness and
   scaling evidence, but canonical end-to-end dataflow is not yet implemented.
4. `agent_control_virtualization` is a semantic reference/compiler input; its
   mock lookup and plaintext runtime are not canonical security components.
5. Historical timing and ORAM experiments remain preserved but are unreachable
   from the V3 entrypoint to be added.
