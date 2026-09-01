# Immutable-failure causal-horizon replay

The replay preserves the recorded private availability sequence and uses the frozen effective public clock. For H5000 and H6000 it deliberately grants the most favourable defensible outcome for the first operation: the already committed READY result is delivered in an added public slot. This makes the replay an upper bound on rescue, not an adverse assumption.

| Horizon | Fixed PIR cutoff | Repair-favourable completion | Decisive reason |
|---|---:|---:|---|
| H4500 | 4089 ms | 0/2 | Immutable observed failure |
| H5000 | 4589 ms | 1/2 | Second descriptor miss remains after cutoff |
| H6000 | 5589 ms | 1/2 | Second intent alone is more than 6420.945812 ms after PIR origin |

Neither predeclared larger horizon reaches 2/2. `ORIGINAL_HORIZON_LADDER_INSUFFICIENT = YES`, `REPLAY_ELIGIBLE_RELIABILITY_H_MS = NONE`, and Section 7 requires an immediate stop before live execution.
