# tau-bench utility results

The current tau2 successor repository was used because the original tau-bench repository marks its tasks as outdated. Twenty mutating retail tasks were selected.

This is a deterministic reference-action replay, not a full LLM tau2 run. It isolates whether the M3 wrapper changes the prescribed action, arguments, step count, or final ledger state.

| Variant | Tasks | Task success | Tool-call correctness | Final-state proxy | pass^k |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline | 20 | 100% | 100% | 100% | not applicable |
| M3 | 20 | 100% | 100% | 100% | not applicable |

This supports functional non-regression only. It does not establish model-level tau2 utility.

