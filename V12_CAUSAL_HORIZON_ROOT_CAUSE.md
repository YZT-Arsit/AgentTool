# V12 causal-horizon root-cause freeze

This document was frozen before effective-clock implementation or new live execution. It preserves all prior failed identities without retry or reinterpretation.

Two facts are independent.

First, action preparation, action commitment, and result delivery used nominal `D_i - L` cutoffs while public dispatch used the no-burst recurrence `E_i = max(D_i, S_(i-1) + Delta)`. This is a genuine clock-consistency defect.

Second, repairing that defect is insufficient for the immutable H3000 trace. Operation 47's descriptor was available no earlier than 3840.726615 ms, while the last effective cutoff among the fixed 300 admission-capable slots was 3543.653121 ms. The repair-favourable replay remains 46/50.

Therefore H=3000 ms is independently insufficient for the retained M=50 depth-50 online causal contract. M remains 50; depth-50 remains required; no outcome-derived reduction is permitted.

The historical failures remain:

- `DEV-TD-CAPACITY50-P10-PIR60`: aborted harness-integrity failure, never retried.
- `DEV-TPCIC-MS-SAME-AGENT-DEPTH50-001`: Microsoft native default-iteration failure, never retried.
- `DEV-MDCC-OA-SAME-AGENT-DEPTH50-001`: integrated canonical 46/50 failure, never retried.
- H3000 effective-clock counterfactual: 46/50, not 50/50.

This is functional/capacity development evidence. It is not timing-privacy evidence.
