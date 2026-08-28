# Adaptive Security Model

## Scope

Stage 9 studies a trusted mediator interacting with an honest-but-curious host that can observe mediation/orchestration metadata. The planner is untrusted. Private authorization, consent, provenance, and binding state remain inside trusted execution or behind ORAM-style accesses. Local mock effects and local consent are trusted. This model does not cover a malicious storage server, real tools, network-destination privacy, unbounded agents, or fine-grained timing privacy.

## Bounded machine

The mediator is a finite state machine

\[
M=(S,A,\delta),
\]

with private state \(\sigma\). A bounded execution under public horizon \(H\) is

\[
\tau_H=(s_0,a_1,s_1,\ldots,a_h,s_h),\quad h\leq H.
\]

The implementation uses an acyclic finite IR and calculates the maximum path length before execution. It does not claim security for an unbounded or recursively self-extending agent loop.

## Host view

The primary structural view is

\[
View_H(\tau)=(n_{round},n_{request},(op_i),(service_i),(bytes_i),(boundary_i)).
\]

It contains mediated round count, state-service request count, ordered operation and service classes, serialized request/response sizes, public round boundaries, and ORAM physical paths when the full observation is evaluated. It never contains logical IDs, real/dummy markers, guard values, permission values, provenance identities, or the derived label.

Fine-grained wall-clock timing is a separate augmented view. The implementation does not shape local-consent delay, and the primary claim excludes it.

## Allowed leakage

For the primary equivalence class, \(\mathcal L(\tau)\) reveals:

- the initial public task schema and action type;
- the public bound \(H\);
- final effect type;
- whether the authorized effect occurred;
- the public success/failure class.

It does not reveal whether authorization or provenance existed initially, whether local consent or an extra verification was required, or how many private mediation rounds would have occurred naturally.

The paired experiments hold the initial task, final synthetic effect arguments, and success outcome equal while varying natural private state fields. There is no experiment-only hidden-bit guard.

## Definition

**Bounded Adaptive Mediation Indistinguishability (BAMI).** For programs admitted under a public horizon \(H\), if

\[
\mathcal L(\tau_0)=\mathcal L(\tau_1),
\]

then the normalized structural views should satisfy

\[
View_H(\tau_0)\approx_c View_H(\tau_1).
\]

In this simulator, equality of round, operation, service, and size sequences is exact; physical ORAM paths are randomized and evaluated statistically. This is bounded trajectory privacy, not full adaptive-agent privacy.

## Assumptions and proof sketch

Assume:

1. each private logical access uses an ORAM interface whose physical path distribution is independent of the logical address;
2. the normalizer emits the same schedule for every private path in one public leakage class;
3. real and dummy state accesses have the same host-visible encoding and cost model;
4. only one real external effect can occur, at the public commit slot;
5. all paths fit \(H\), or the entire public program class fails closed before any external effect;
6. trusted-runtime computation, local consent content, and fine-grained timing are not observed.

The compiler fixes the number of rounds from \(H\), fixes three indistinguishable internal access slots per round, and places the public effect at the final slot. Replacing a real internal operation with a dummy therefore preserves the structural view. ORAM security supplies logical-address indistinguishability for each slot. A hybrid argument replacing real internal slots one at a time yields computationally indistinguishable full views. External effects are identical by the leakage-class premise and occur at the same commit slot. The implementation demonstrates the structural part and an ORAM trace simulation; it is not a production cryptographic proof.

## Safety and overflow

Authorization safety dominates privacy. A denial never becomes an effect. The implementation never issues dummy external effects.

If the state machine's maximum path exceeds \(H\), the compiler marks the entire public program class as overflow. Execution emits the fixed internal schedule, returns public `HORIZON_EXCEEDED`, and commits no effect. This avoids privately branching into fallback behavior and avoids silently truncating authorization logic.

## Demonstrated boundary

At \(H=5\), B2 produced exact structural equality and classifier AUC 0.500 across all evaluated scenarios. Raw timing AUC remained high for the consent scenario because a real local interaction is slower than trusted dummy work. Therefore:

```text
STRUCTURAL PRIVACY: SUPPORTED IN THE EVALUATED BOUND
TIMING PRIVACY: OUT OF SCOPE
UNBOUNDED PRIVACY: NOT CLAIMED
```
