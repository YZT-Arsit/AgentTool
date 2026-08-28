# IR-v1 baseline freeze

## Permanent result

IR-v1 is permanently reserved at **48.39% corpus coverage**. The exact value is `0.4838884375846195`: 3,574 of 7,386 recorded behavior instances were either compiled (1,708) or assigned to a shared primitive (1,866), and 3,812 were unsupported.

This is a historical measurement, not a mutable label set. Unsupported rows will not be relabeled in place, even when later inspection finds that an extractor row is overbroad or that a future primitive could support a restricted subset.

## Frozen corpus

| Framework | Pinned commit | Files | Corpus roots |
| --- | --- | ---: | --- |
| OpenAI Agents SDK | `a40ae9803e6b7a79faa246293f56adb100d5868b` | 216 | `examples/**` |
| Microsoft Agent Framework | `af461de51da16f5cb800ff7febc0f8f96355607a` | 98 | `python/tests/samples/**`; `python/packages/core/tests/**` |
| Total | — | **314** | — |

The normalized corpus-membership digest is `0DE43BB61CA22638445FC1B52662A9A8F58CC6937DD0D79C6C5A86E949EC0E6D`. Exact artifact hashes, counts, commits, and rules are machine-readable in `IR_V1_BASELINE_MANIFEST.json`.

## Versioning rule

- `CORPUS_MANIFEST.csv`, `CORPUS_BEHAVIOR_INSTANCES.csv`, `CORPUS_IR_COVERAGE.csv`, `CORPUS_IR_AUDIT.md`, `SEMANTIC_FIDELITY_RESULTS.csv`, and `SEMANTIC_FAILURE_CASES.csv` are the immutable IR-v1 evidence package.
- `scripts/run_corpus_ir_audit.py` refuses to overwrite these files after the freeze manifest exists and first verifies all six checksums.
- Any IR-v2 must write new, versioned artifacts and evaluate the exact same 314-path corpus at the same two commits.
- IR-v2 coverage must be reported alongside—not substituted for—the IR-v1 48.39% baseline.
- Feasibility labels in the unsupported decomposition are not projected coverage and must never be summed as if they were successful lowerings.

## Dynamic evidence boundary

Dynamic fidelity is evaluated separately from static coverage. Additional executions on IR-v1-supported strata may add evidence about current semantics, but cannot alter any static IR-v1 disposition or the 48.39% result.
