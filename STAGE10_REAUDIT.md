# Stage-10 Reaudit

## Decision

```text
STAGE-10 EVIDENCE STILL VALID: YES
STAGE-10 SECURITY DEFINITION: REVISED
```

The Stage-10 empirical result is unaffected: two independent public approval runtimes naturally expose a one-versus-two mediation continuation for different private approval states while producing the same real effect once. B0 and B1 remain structurally distinguishable; B2 equalizes the bounded structural schedule with zero dummy external effects.

The result does not establish timing privacy. Stage 10 explicitly excluded it, and the recorded OpenAI Agents SDK means (`2.129 ms` approval present versus `3.307 ms` approval absent) show why Stage 11 must add it to the observer.

## What survives unchanged

- Microsoft Agent Framework and OpenAI Agents SDK provenance and unmodified semantics;
- same initial public task and byte-equal final synthetic effect;
- B0/B1 structural AUC `1.000 +/- 0.000`;
- B2 structural AUC `0.500 +/- 0.000` and exact structural equality;
- common Stage-9 Mediation IR and `AdaptiveNormalizer`;
- `H=5`, 15 ORAM accesses, and zero dummy external effects;
- the conclusion that per-action mediation privacy does not imply bounded adaptive mediation privacy.

## What changes

1. `View_H` now includes scheduled timing, message sizes, and endpoint/dispatch observations.
2. The public configuration includes `(H, Delta, B, W)` and the complete public effect projection.
3. The theorem is observer-specific and states non-collusion/trust assumptions.
4. Same-success approval paths enter a public approval window and release only at its boundary.
5. B2 is retained as the structural mechanism; M3 adds size/cadence shaping.
6. Private agent routing is a separable front-end component. It does not retroactively alter the Stage-10 claim.

## Audit of possible overclaim

The Stage-10 report correctly rated the normalizer incremental and the security definition `NEEDS REVISION`. Stage 11 repairs the definition but does not turn the normalizer into a new oblivious-computation primitive. The strongest defensible claim remains agent-specific measurement, formal leakage-class design, and effect-safe instantiation.
