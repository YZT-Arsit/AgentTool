# Structural and size residual audit

Every M3 trace has five slots, slots 1–5 in order, 16,384 receiver-visible bytes per slot, and 15 ORAM physical accesses. No private label, family, branch, or real/dummy indicator occurs in the serialized host trace.

Across both runtimes (384 M3 episodes, grouped-task split):

| Feature | Model | AUC | 95% CI | Permutation | p |
|---|---|---:|---:|---:|---:|
| Structural | Logistic regression | 0.518 | 0.479–0.570 | 0.497 | 0.176 |
| Structural | Random forest | 0.488 | 0.448–0.538 | 0.495 | 0.647 |
| Size | Logistic regression | 0.500 | 0.500–0.500 | 0.500 | 1.000 |
| Size | Random forest | 0.500 | 0.500–0.500 | 0.500 | 1.000 |

The earlier structural AUC 0.518 is consistent with sampling/classifier variation in this repeated corpus; it is not reproducible evidence of a structural field leak. Actual receiver-visible size equality passes exactly. This finding is development evidence because the corpus was inspected during repair.
