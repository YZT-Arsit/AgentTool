# Final Security Definition — historical, superseded for Agent invocation

The active full-domain target goal has no public cohort and does not use ORAM
or visible named cover sets to hide Agent/Tool activation.

## Classification

```text
SOUND WITH EXPLICIT ASSUMPTIONS
```

This is a structural, bounded, observer-specific definition. It includes public-bucket message size and fixed-cadence timing, but not microarchitectural leakage or arbitrary collusion.

## 1. Public configuration and leakage

Let public configuration

```text
p = (runtime, public task projection, capability class,
     candidate-set size/class, H, Delta, B, W,
     overflow policy, public effect projection, public outcome class)
```

contain every value that the named observer is allowed to learn. The **public effect projection** includes every effect attribute visible to that observer, not merely a tool name.

Executions `x0` and `x1` are leakage-equivalent, written `x0 ~L,p x1`, only if they have equal `p`, including the same successful effect and effect count. They may differ in:

- concrete selected agent and registry index, where that value is protected from the named observer;
- prior approval/consent/authorization state;
- provenance/history state;
- whether approval, persistence, verification, retry, or resume occurred;
- natural internal round count/order and natural internal message sizes/timing.

ALLOW and DENY, success and overflow, or two publicly different effects are not placed in the same class.

## 2. Observer view

For named observer `O`, `View^O_H(x)` includes all events visible within the public horizon:

- registry/PIR/ORAM physical transcript exposed to `O`;
- destination endpoint, relay, or cover slot observations;
- mediation service and operation-class sequence;
- round and message count;
- request/response size bucket sequence;
- scheduled send/receive time, cadence, burst, and idle-gap pattern at the declared resolution;
- public approval-epoch boundaries (not whether a trusted local prompt occurred);
- public effect commit slot and complete public effect projection;
- sanitized error/outcome class.

`View` excludes trusted memory, plaintext, logical addresses behind a secure ORAM/PIR boundary, local approval UI events, cryptographic secrets, and microarchitectural signals.

## 3. Bounded oblivious agent-mediation privacy

For security parameter `lambda`, public configuration `p`, named PPT observer `O`, and every pair `x0 ~L,p x1` that fits `H`, require:

```text
| Pr[O(View^O_H(x0; r0)) = 1]
  - Pr[O(View^O_H(x1; r1)) = 1] | <= negl(lambda)
```

where `r0` and `r1` include fresh cryptographic/ORAM randomness. For the deterministic structural projection used in the controlled prototype, the non-physical schedule, size sequence, and cadence sequence are exactly equal.

## 4. Explicit assumptions

1. **Named observer/non-collusion.** The theorem is instantiated separately for registry host, infrastructure observer, and mediation host. Collusion with the trusted resolver or selected specialist is excluded where it trivially reveals selection.
2. **ORAM.** Equal-length sequences of logical private-state accesses produce computationally indistinguishable physical storage views. Client position-map/stash state remains trusted.
3. **PIR/SPIR/OT.** Where used, the selected scheme hides the client index from the registry under its stated server, setup, and collusion assumptions. Stage 11's R1 code is only an ideal leakage abstraction.
4. **Private routing.** If the routing provider must not learn the prompt, routing runs in a trusted local resolver/TEE or a specified MPC/FHE/2PC protocol. PIR alone is insufficient.
5. **Dispatch.** Concrete endpoint privacy from infrastructure requires full cover or a shared private relay/dispatcher with an equivalent externally visible schedule. Direct distinct endpoints do not satisfy the definition.
6. **Cryptographic envelopes.** Real and cover internal envelopes are indistinguishable to the relevant host, including length and authentication/error behavior.
7. **Fixed size.** Each message is padded to public bucket/bound `B`; oversize messages use a public overflow class or fail closed before an effect.
8. **Fixed cadence.** The transport enforces public round duration `Delta`, approval window `W`, and horizon `H` at the observer boundary. Scheduler jitter is either bounded inside a public tolerance bucket or included in the trace and equalized.
9. **Effect discipline.** Exactly one authorized real effect may occur at the public commit slot. Cover operations and unused slots cannot cross the effect gate. No dummy external effect is generated.
10. **Errors.** Denial, timeout, malformed state, and overflow are equalized within a class or separated as public outcome classes. Errors do not expose private reasons.

## 5. Proof sketch

Take leakage-equivalent successful executions.

1. The public compiler emits the same `H`, `Delta`, `B`, `W`, operation-class slots, and commit slot.
2. The routing front end emits the same capability-class projection. For observer B, PIR/ORAM replaces the secret registry index with an indistinguishable protected query/access. For observer C, full cover or an assumed private dispatcher emits the same destination-slot set; direct dispatch is excluded.
3. Every real or unused internal mediation slot issues an equal-shaped protected access. ORAM hides the logical address; envelope encryption/padding hides real versus cover content.
4. Fixed-size framing makes the message-size sequence equal. Fixed-cadence release makes the round and idle-gap sequence equal at the declared resolution. Both approval states wait through the same public approval epoch; only the state needing approval creates a trusted local prompt.
5. The trusted effect gate binds the one real authorized effect to the common public commit slot. Because the compared effect projection and outcome are equal, this public event is equal. Cover slots cannot create effects.

Hybrid replacement of indistinguishable protected accesses/envelopes then yields computationally indistinguishable views. The argument is conditional on each listed primitive and transport assumption; it is not a proof of those primitives.

## 6. Failure and horizon semantics

- If the IR's required rounds exceed `H`, the execution fails closed before dispatch/effect under a public overflow outcome.
- If required approval does not arrive by `W`, the execution fails closed at the public epoch boundary.
- If a message exceeds `B`, it enters a declared larger public bucket or fails closed consistently.
- Denied effects remain denied. Privacy transformation cannot convert DENY to ALLOW.

These paths are compared only with executions in the same public outcome/overflow class.

## 7. Limits

The definition does not hide selection from the selected specialist, tolerate collusion with the trusted resolver, or cover CPU/cache/power leakage. It gives epoch/cadence timing privacy, not continuous-time or global congestion privacy. The controlled scheduler records contractual offsets; live public-runtime transport enforcement remains a P0 experiment.
