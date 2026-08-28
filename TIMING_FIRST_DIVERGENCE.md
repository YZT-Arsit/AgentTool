# Timing first-divergence analysis

## Answer

Private correlation exists naturally at T1 (private work ready), where the diagnostic classifier reaches AUC 1.0. In the original live implementation, correlation was reintroduced at T7 because a busy-wait sender and receiver shared the Python GIL: all arrivals were observed as a post-epoch burst. Moving the receiver to a separate process repaired that defect.

The frozen development artifact still shows the earliest residual public-boundary divergence at T4/T6:

- Microsoft provenance: T4 release-slip RF grouped-task AUC 0.602, p=0.039.
- Microsoft authorization: T4-to-T6 RF grouped-task AUC 0.624, p=0.039.
- OpenAI authorization: T4-to-T6 LR grouped-task AUC 0.677, p=0.020.
- OpenAI authorization: T6-to-T7 LR grouped-task AUC 0.710, 95% CI 0.611–0.789, p=0.020.

Thus the Stage-12 hypothesis was partly correct: shaping above the actual receiver boundary and same-process receiver scheduling caused leakage. Repairing those defects removed the broad pooled receiver-arrival signal, but did not eliminate all state-family timing correlation.

## T0–T9 interpretation

| Boundary | Meaning | Finding |
|---|---|---|
| T0–T2 | trusted private work/readiness/queue | strongly state-dependent by design; not public |
| T3 | public scheduled deadline | deterministic |
| T4 | actual sender release | residual state-conditioned slip exists |
| T5–T6 | serialization complete/send invoked | fixed size, but micro-to-millisecond scheduling variation remains |
| T7–T8 | separate-process arrival/processing | broad GIL burst repaired; subgroup signal remains |
| T9 | public commit visible | one Microsoft authorization attack reached AUC 0.795 on a small within-task holdout |

## Root cause conclusion

The first defect was an incorrect observer boundary. The remaining evidence is consistent with state-correlated runtime/OS scheduling and deadline-slip tails, not merely state-independent network noise. The experiment does not localize or claim protection against microarchitectural causes.
