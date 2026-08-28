# Untouched semantic holdout report

## Status

The permanent IR-v1 result remains **3,574/7,386 = 48.39%**. The prior IR-v2
72/72 result is **development regression evidence only** because those cases
guided the Tool-loop repair.

The new holdout was frozen before execution as
`SEMANTIC-HOLDOUT-V2-20260828`: 20 source-traceable cases from seven official
pinned source files, split across both frameworks, with 14 Tool-containing
cases. Manifest SHA-256:
`a362d3d0e2c9f989cf973eb932227467007986f4bf6e5e8a0f0e1c69bb917d9d`.

It was executed once. It must not be rerun or tuned.

Independently, the already-used development strata were rerun into the new
versioned artifact `SEMANTIC_FIDELITY_V2_DEVELOPMENT_REGRESSION_20260828.csv`:
72/72 passed, including 18/18 Tool cases. This confirms non-regression only and
does not repair or substitute for the holdout.

| Outcome | Cases |
| --- | ---: |
| Valid semantic pass | 8 |
| Valid semantic mismatch | 0 |
| Harness-invalid / not semantically adjudicated | 12 |
| Total | 20 |

Framework valid passes were OpenAI 2/12 and Microsoft 6/8, but those fractions
are **not fidelity rates** because the remaining cases did not reach semantic
comparison. Four of 14 Tool-containing cases validly passed.

## Preserved harness failures

- Six OpenAI Tool cases failed during native-object construction because the
  holdout runner created an illegal Pydantic Tool schema from a `**_` synthetic
  wrapper.
- Two OpenAI handoff cases failed because the frozen script actor
  `triage_agent` was not mapped to the runner's root alias.
- Four OpenAI/Microsoft Agent-as-Tool cases failed because frozen actor
  `parent` was not mapped to the runner's root alias.

These are evaluator defects, not evidence that the IR semantics differ. They are
also not passes. The raw immutable outcomes remain in
`SEMANTIC_HOLDOUT_V2_RESULTS.csv`; no case was removed, relabeled, or rerun.

## Conclusion

The requested untouched semantic confirmation is **INCOMPLETE**. The eight
valid cases support only their final/Tool strata. Agent-as-Tool has separate
development tests for both native object forms, but no untouched holdout claim
is made. A future confirmatory holdout must use new, previously unseen official
cases and a separately pretested generic harness; repairing and rerunning this
manifest would create development evidence, not an untouched holdout.
