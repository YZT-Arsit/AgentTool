# Final Security Definition Audit

## Decision

```text
NEEDS REVISION
```

The Stage-9 proof idea is sound, but the displayed implication is underspecified. Equality of leakage labels alone does not prove view indistinguishability; the theorem must quantify the runtime, adversary, randomness, effect projection, and excluded channels.

## Corrected leakage class

For public configuration `p` and horizon `H`, write `x0 ~L x1` only when both executions have equal:

- initial public task projection;
- runtime/framework identity and public configuration;
- public horizon and overflow policy;
- final public effect projection, including every effect attribute the observer can see, not merely the tool type;
- public success/failure class;
- number of public top-level tasks/episodes.

The protected differences may include:

- prior approval or consent state;
- whether an approval/consent action was required;
- authorization-persistence path;
- retry/resume count;
- private provenance path;
- number and order of internal mediation rounds, up to `H`.

The main experiment is stricter than the minimum class: the initial task, tool name, recipient, body, successful output, and single effect record are byte-for-byte equal.

## Public leakage audit

| Item | Classification | Qualification |
|---|---|---|
| Initial task | PUBLIC | Public projection; private arguments would need handles or separate protection |
| Tool identity | PUBLIC | `send_message` in this experiment |
| Final effect | PUBLIC | All observer-visible effect attributes belong in the leakage class |
| Success/failure | PUBLIC | Compared only within the same public outcome class |
| Public horizon | PUBLIC | `H=5` |
| Number of internal rounds | PRIVATE | Protected within the bounded class |
| Approval occurrence | PRIVATE | Protected |
| Retry/resume occurrence | PRIVATE | Protected |
| Consent occurrence | PRIVATE | Protected |
| Runtime framework | PUBLIC | Microsoft Agent Framework versus OpenAI Agents SDK is not hidden |
| Fine-grained timing | OUT OF SCOPE | Recorded only as overhead; not covered by the theorem |

## Revised proof sketch

Let `View_H(x; r)` be the structural host view emitted by B2 for execution `x` using cryptographic/runtime randomness `r`. For any PPT structural observer `A` and any `x0 ~L x1` whose public class fits horizon `H`, require:

```text
| Pr[A(View_H(x0; r0)) = 1] - Pr[A(View_H(x1; r1)) = 1] | <= negl(lambda).
```

The argument is defensible under these explicit premises:

1. The Stage-9 compiler derives the same `H` public slots and commit slot from the common public IR/configuration.
2. Every slot emits the same service/operation/size shape.
3. Each real or dummy internal logical access is implemented through a secure ORAM interface, so its physical view is computationally indistinguishable at equal access counts.
4. Record encryption/padding makes real and dummy payloads indistinguishable at the trace boundary.
5. External effects are held inside the trusted coordinator and released only in the common public commit slot.
6. No dummy external effect is issued.
7. Overflow, denial, crash, and malformed-state behavior are equalized or placed in separate public classes and fail before an effect.
8. Error messages, application-level callbacks, telemetry, and serialization do not separately reveal protected state.
9. Timing, resource contention, and microarchitectural leakage are explicitly excluded.

Given these premises, the visible schedule is identical and the only randomized difference is protected by ORAM/payload indistinguishability, so the structural views are computationally indistinguishable.

## Why the original formula needs revision

The shorthand

```text
L(tau0) = L(tau1) => View_H(tau0) ~=c View_H(tau1)
```

omits four necessary boundaries:

- `L` must contain all actually public effect attributes, not only an effect type;
- executions that exceed `H` need a class-wide fail-closed rule;
- the approximation depends on ORAM, encryption/padding, and trusted-coordinator assumptions;
- structural equality does not imply timing equality.

These are repairable specification gaps, not a counterexample to the implemented structural mechanism.

