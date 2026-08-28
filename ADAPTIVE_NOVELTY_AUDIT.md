# Adaptive Novelty Audit

## Gate ratings

| Gate | Rating | Reason |
|---|---|---|
| N1 — per-action mediation leakage | NOT NOVEL | Stages 1–8 and prior oblivious-systems work already establish access/control-flow leakage. |
| N2 — adaptive mediation leakage | MODERATE | Same-task/same-effect approval and provenance state changes multi-round mediation; one public runtime independently exhibits the approval case. |
| N3 — bounded adaptive mediation definition | MODERATE | The leakage class, public effect occurrence, bounded horizon, no-dummy-effect rule, and fail-closed overflow give a precise agent-security formulation. |
| N4 — mediation IR | WEAK | The annotated finite IR is useful and inspectable but deliberately small and unsurprising. |
| N5 — adaptive normalizer/compiler | WEAK | It is a straightforward fixed-horizon control-flow normalizer; no new oblivious primitive or scheduling algorithm is shown. |
| N6 — real/public-runtime measurement | MODERATE | L2 was achieved on one unmodified public runtime path, but only with boundary instrumentation and one framework. |

The continuation gate passes because N2, N3, and N6 are MODERATE. It does not pass on mechanism novelty alone.

## Strongest rejection

> General oblivious computation already says secret-dependent control flow must be normalized. This project merely builds a tiny bounded state machine around an agent tool call.

Classification:

```text
PARTIALLY DEFEATED
```

Evidence against the rejection:

- Microsoft Agent Framework's existing persistent standing-approval state naturally changes application-round structure while preserving the same local effect.
- B1 directly demonstrates a composition failure: individually canonical rounds do not compose into trajectory privacy.
- the definition treats authorization denial and actual effect occurrence explicitly;
- the mechanism forbids dummy external effects and fixes a real commit point;
- three different private state semantics and two effects use one transformation.

Evidence supporting the rejection:

- the compiler is a small bounded padding transformation;
- the proof is a specialization of familiar ORAM plus fixed-control-flow reasoning;
- one public runtime is insufficient to establish prevalence;
- timing is unprotected;
- no independent expert prior-art review has established novelty.

## Strongest accurate acceptance argument

Secure-agent runtimes can make individual state accesses or mediation rounds locally canonical yet still expose adaptive trajectories: private authorization and provenance state changes whether consent, persistence, verification, and subsequent mediation actions occur even when the same public effect is produced. Stage 9 formalizes a bounded leakage class and demonstrates an effect-safe fixed-horizon transformation with no dummy external effects. One unmodified public approval runtime corroborates the natural trajectory counterexample.

Every clause above is supported by the Stage-9 artifacts. It makes no claim of a new ORAM, new padding primitive, or general-purpose oblivious compiler.

## Decision

```text
CONTRIBUTION STRENGTH: MODERATE
ICASSP MAINLINE: CONDITIONAL
```

The mainline is viable only if framed around the agent-security composition boundary, L2 measurement, leakage definition, and effect-safe constraints. A mechanism-first novelty claim is not defensible from this prototype.
