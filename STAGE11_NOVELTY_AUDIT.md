# Stage-11 Novelty Audit

## Ratings

| Component | Rating | Reason |
|---|---|---|
| Adaptive agent-mediation leakage | MODERATE | Two public runtimes, same-task/same-effect approval paths, and the per-action composition failure remain agent-specific evidence; secret control-flow leakage is classical. |
| Bounded adaptive definition with size/cadence | MODERATE | The named-observer, public-effect, approval-window, and no-dummy-effect class is useful; fixed schedules and padding are known. |
| Mediation IR | MODERATE | Reused across two runtimes and cleanly extended; still a small finite IR. |
| Normalizer/M3 scheduler | INCREMENTAL | Fixed horizon, message padding, and cadence follow generic oblivious-computation/traffic-shaping principles. |
| Private prompt routing | NOT NOVEL | PPRoute already performs prompt-dependent LLM routing under MPC. |
| Selected expert/dispatch privacy | WEAK | CryptoMoE already protects expert routing/dispatch; remote agent endpoints/effects differ but use standard cover/relay trade-offs. |
| Effect-safe no-dummy adaptation | MODERATE | Important for tool-agent semantics and preserved across routing/mediation; not a new transaction primitive. |
| Combined method coherence | MODERATE | One view can describe both layers, but their observers/primitives and evaluation burdens differ. |

## Private-routing novelty gate

Strongest rejection:

> PPRoute already performs privacy-preserving LLM routing under secure computation, CryptoMoE already hides expert routing and implements secure expert dispatch, and the remaining endpoint-hiding options are standard cover traffic or trusted relays.

```text
Classification: NOT DEFEATED
```

The remote specialist-agent setting adds meaningful effect and administrative boundaries, but no qualifying sublinear/full-privacy dispatch was produced. Routing must remain an implementation component, not the paper's novelty claim.

## Adaptive-mediation novelty gate

Strongest rejection:

> Generic oblivious computation already handles secret-dependent bounded state machines, so the method is fixed padding around approval middleware.

```text
Classification: PARTIALLY DEFEATED
```

The rejection remains correct at the primitive level. It is weakened by the two-runtime natural evidence, the same-final-effect class, the demonstrated failure of per-action protection, the shared IR, and the rule that cover work may never produce external effects. Adding private routing does not strengthen this answer and could distract from it.

## Strongest accurate acceptance argument

> Private authorization and provenance state changes approval, persistence, retry, and resume structure in two independent public tool-agent runtimes even when the public task and real effect are the same. A shared bounded mediation IR equalizes that structure, size, and public cadence while retaining exactly one authorized effect and producing no dummy external effects. The contribution is the agent-specific composition gap, evidence, leakage class, and effect-safe systems instantiation—not a new ORAM, PIR, secure-routing, or padding primitive.

## Final novelty boundary

Defensible:

1. two-runtime measurement of adaptive security-mediation metadata leakage;
2. same-task/same-effect observer definition including size/cadence and approval epochs;
3. common IR and effect-safe bounded instantiation;
4. observer-specific demonstration that registry privacy is not endpoint privacy.

Not defensible:

- first private routing or secure expert dispatch;
- a new ORAM/PIR primitive or improvement;
- sublinear full-cover-equivalent remote dispatch;
- live network timing privacy before P0 completion;
- one universal non-colluding/colluding security claim.
