# Frozen Experiment Matrix V7

Status: **FROZEN BEFORE CONFIRMATORY PRIVACY EXECUTION**.

The machine-readable matrix is `EXPERIMENT_MATRIX_V7.csv`. It fixes eleven
experiment groups covering PIR selection, semantic correctness, destination,
size, long-horizon structure, route leakage, repeated observation,
cross-session linkage, performance, recovery, and the resource-observer
boundary.

Rules fixed with the matrix:

- payload confidentiality is orthogonal and equal across baselines;
- every paired privacy comparison is invalid if either arm fails functionally;
- exact structural/size equality precedes classifier checks;
- classifier features exclude timing in V7;
- the 24-case action holdout is one-shot and cannot be tuned or replaced;
- `STRICT` and `ENTERPRISE_EFFICIENT` are different leakage profiles and are
  never pooled into one indistinguishability claim;
- SimplePIR is audited as the existing primitive, not redesigned; and
- timing, packet release, resource privacy, hardware attestation, and
  hardware-anchored rollback remain OPEN/NOT TESTED.
