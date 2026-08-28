# Final method freeze

## Frozen component

The development implementation of the finite paced-cover transport primitive is frozen:

- persistent prewarmed connection;
- separate fixed-affinity sender and receiver processes;
- sender-chosen acknowledged epoch start;
- fixed five-slot schedule;
- 16,384-byte envelopes;
- fixed ORAM transcript count;
- fixed pre-commit guard;
- fail-closed late proposals;
- zero dummy external effects.

No further tuning may use the current 40-task corpus as a final test.

## Not frozen as a validated claim

High-assurance timing privacy and full agent-trajectory privacy are not validated. The present experiment is one-directional and finite. The eventual design requires persistent secret-independent queued cover channels in both request and response directions, with all protected worker/RPC activation routed through the Privacy Kernel boundary.

## Required confirmatory step

Create a fresh untouched holdout only after freezing code, cadence-selection rules, feature sets, thresholds, and failure semantics. Confirm both directions under an honest-but-curious compute-plane observer. Predeclare overflow as either public leakage or a protected event, and evaluate availability/effect equivalence separately. No new ORAM or PIR mechanism is needed.
