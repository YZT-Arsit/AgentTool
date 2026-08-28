# IR-v1 dynamic fidelity continuation

## Independent continuation result

The continuation executed 72 fresh local deterministic cases using seeds 100–117. It used the existing IR-v1 compiler and runtime unchanged and wrote new versioned outputs; it did not overwrite the frozen `SEMANTIC_FIDELITY_RESULTS.csv` or `SEMANTIC_FAILURE_CASES.csv`.

| Supported stratum | Executions | Exact semantic equivalence | Fidelity |
| --- | ---: | ---: | ---: |
| OpenAI simple | 18 | 18 | 100% |
| OpenAI static handoff | 18 | 18 | 100% |
| Microsoft simple | 18 | 18 | 100% |
| OpenAI Tool | 18 | 0 | 0% |
| **Total** | **72** | **54** | **75%** |

All 18 Tool failures reproduce the same mismatch set: `tool_arguments`, `state_updates`, `external_effect_sequence`, `effect_count`, `termination_class`, `sanitized_final_result`, and `model_calls`. IR-v1 stores a Tool target handle but does not reproduce exact arguments, execute the effect, or model the post-Tool LLM transition. This is a fidelity failure on a nominally shared-primitive stratum and must not be hidden by the static 48.39% metric.

The full projections are in `IR_V1_DYNAMIC_FIDELITY_CONTINUATION.csv`; the 18 failing rows are in `IR_V1_DYNAMIC_FAILURE_CASES.csv`.

## Interpretation boundary

- This continuation strengthens evidence only for the three passing current strata.
- It supplies direct negative evidence for current Tool semantic fidelity.
- It does not relabel any static corpus row, change corpus membership, or alter IR-v1 coverage.
- IR-v2 must address the Tool continuation/effect model explicitly and must be evaluated as a new version on the frozen corpus.
