# Canonical Threat Model V3

Status: **CANONICAL ACTIVE**.

## Trusted components

- Privacy Kernel: private Agent selection, SimplePIR client state, capsule
  plaintext/cache, logical control state, keys, trusted encoder, and result
  decryption.
- CommonActionGateway V2 Worker and Pacer, including private rings,
  authorization/EffectGate state, and local provider adapters.
- Local synthetic user and local provider emulators for the experiment.

## Observers

### O_registry — untrusted Agent registry / PIR server

Owns the capsule database and observes the public database shape and valid
SimplePIR server transcript. It must not receive the selected index, Agent ID,
capsule plaintext, or client recovery state. The base model excludes collusion
with the Privacy Kernel.

### O_agentcloud — untrusted Cloud Slot Proxy U

Observes the public profile ID, public session/epoch and slot identifiers,
fixed frame width, fixed request/response schedule, CommonActionGateway
destination, opaque ciphertext, connection lifetime, and socket-boundary
metadata at the declared resolution. U must not receive keys or any plaintext
Agent/action/provider/result field.

The LLM planner, specialist workers, and Agent execution server are treated as
part of this honest-but-curious untrusted compute plane unless a heavy primitive
is explicitly placed behind the trusted Gateway boundary.

### O_gateway — trusted Gateway

The Gateway necessarily decrypts and routes one real provider action. It is not
the privacy adversary in the base model. Collusion between the Gateway and U is
excluded.

### O_provider — downstream provider

A provider necessarily sees its own plaintext request and timing. The base claim
does not hide an operation from the provider that executes it and excludes
cross-provider collusion. U sees only the common Gateway endpoint, not the local
provider destination.

## Public leakage

Public leakage includes protocol/profile version, database dimensions, public
PIR/control/I/O schedules, public session policy, fixed frame bucket, common
Gateway endpoint, public outcome class, and an agreed public effect projection.
Two executions are compared only when these values match.

## Protected values and metadata

- registry index and logical Agent identity;
- capsule/control-state plaintext;
- logical handoff target;
- private opcode/action and Tool/provider identity as viewed by U;
- prompts, Tool arguments, and results;
- real versus dummy PIR/control/I/O slot use;
- private completion/progress within a fixed public schedule;
- repeated Agent/Tool identity and frequency, subject to the declared view.

## Integrity and robustness

Active malformed, replayed, reordered, duplicate, wrong-direction,
wrong-session, and wrong-profile frames are local robustness tests. They do not
silently broaden the confidentiality adversary into a fully malicious cloud.
Failures must produce a predeclared public outcome shape and may not reveal a
private reason.

## Explicit exclusions

- Gateway/Privacy-Kernel compromise or collusion with U;
- cross-provider or registry-plus-kernel collusion;
- global Internet traffic analysis or independently observed remote provider
  destinations;
- microarchitectural, cache, power, GPU, performance-counter, or fine-grained
  resource side channels inside trusted components;
- packet-level timing for TCP, remote-provider GPU telemetry, or arbitrary human
  response timing;
- malicious model/tool semantics, prompt-injection defense, and arbitrary
  Python/native Agent compilation.

Windows Gateway V2 measurements are development evidence only. Timing privacy
remains unvalidated until a fresh, frozen Linux reference-host experiment
satisfies the prescribed isolation and confirmatory discipline.

## Phase-0 audit

The prior vague “infrastructure observer” terminology is superseded. Canonical
reports must name `O_registry`, `O_agentcloud`, `O_gateway`, or `O_provider` and
must state the exact link/process observed.

