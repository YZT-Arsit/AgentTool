# Canonical V3 Structural/Size Falsification

## Scope

This is an offline sanity/falsification analysis over 42 Linux canonical
episodes: six independent repetitions of seven bounded workflows. Attacker
features contain only declared structural/size metadata: event count, direction
counts, public slot/session counts, minimum/maximum/total frame bytes, and
destination count. Timing, ciphertext bytes, and private truth are not silently
mixed into this result.

All 42 feature vectors are exactly equal. The symbolic equality result is the
primary evidence; classifiers are only sanity checks.

## Results

| Attack | Episodes | Model(s) | Metric | Result | Chance | Permutation p |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| Agent identity, 7 classes | 42 | Logistic/RF | accuracy | 0.1429 | 0.1429 | 1.000 |
| Tool identity alpha vs beta | 12 | Logistic/RF | ROC-AUC | 0.5000 | 0.5000 | 1.000 |
| Private branch state | 12 | Logistic/RF | ROC-AUC | 0.5000 | 0.5000 | 1.000 |
| Action family, 3 classes | 18 | Logistic/RF | accuracy | 0.3333 | 0.3333 | 1.000 |

The small test sets give wide bootstrap intervals for predicted accuracy. They
do not create uncertainty about the exact structural feature equality, but they
do prevent treating the classifier rows as a broad statistical privacy proof.

## Intentionally unclosed attacks

Repeated-Agent, Agent-frequency, rare-Agent, transition-pattern, and
cross-session linkability attacks are `NOT_TESTED_NO_CANONICAL_LONG_HORIZON_WORKLOAD`.
The six repeated executions here do not encode the required multi-round hidden
sequence semantics, so relabeling them as long-horizon tests would be invalid.

## Conclusion

`STRUCTURAL_PRIVACY` and `SIZE_PRIVACY` are PASS only for the evaluated bounded
observer/features/workflows. This report does not establish timing, resource,
packet-level, long-horizon, or corpus-wide privacy.

Raw public traces, separately serialized private ground truth, and machine
results are under `results_canonical_v3/security_falsification_20260827/`.
The transfer archive SHA-256 is
`f64fd8de066ddbb3e18f74c1c37dd9637b15aa830e0940754f10b3d60962cdef`.
