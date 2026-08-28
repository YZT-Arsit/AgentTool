# Whole-workflow executable coverage on the frozen 314-file corpus

## Result and denominator discipline

This audit uses the exact 314 paths and pinned commits in `CORPUS_MANIFEST.csv`.
It does **not** replace either frozen behavior-instance result:

- IR-v1: 3,574/7,386 = **48.39%** (permanent baseline).
- IR-v2: 72/72 = **development regression only**; those cases guided the Tool-loop repair.

The conservative executable unit is a source file containing at least one Agent
or workflow constructor. This avoids inventing workflow boundaries that the
static extractor did not prove. A unit is `FULLY_EXECUTABLE` only when every
non-artifact control behavior found in that source file is in the currently
executable instructions/model/Tool/handoff/termination core. Consequently this
is a strict source-file workflow measure, not a claim that every constructor in
a partially executable file fails.

| Status | Source-file workflow units | Meaning |
| --- | ---: | --- |
| Fully executable | 33 | All detected non-artifact behavior is executable by the tested core. |
| Partially executable | 97 | At least one executable behavior and at least one unresolved behavior coexist. |
| Unsupported | 21 | No executable-supported behavior was established for the unit. |
| **Total workflow units** | **151** | Files with at least one Agent/workflow constructor. |
| Non-workflow corpus files | 163 | Retained in the 314-file corpus but excluded from this distinct workflow-unit denominator. |

| Framework | Fully | Partial | Unsupported | Total |
| --- | ---: | ---: | ---: | ---: |
| OpenAI Agents SDK | 33 | 76 | 0 | 109 |
| Microsoft Agent Framework | 0 | 21 | 21 | 42 |

The low Microsoft whole-file result is a negative finding: large core test files
combine supported Agent behavior with persistence, middleware, session, and
workflow constructs that the current executable substrate does not close.

Machine-readable per-file evidence is in
`WHOLE_WORKFLOW_EXECUTABLE_COVERAGE_V2.csv`; the summary is in the adjacent JSON.
The earlier complete 1,099-file materialized-checkout census remains
`CORPUS_FILE_INCLUSION_AUDIT.csv`. It records all 314 included and 785 excluded
files with reasons; `CORPUS_FILE_AUDIT.md` explains why the 314 entered the
frozen corpus.

## Limits

This status is based on statically detected constructs plus executable semantic
support already tested. It is not an estimated IR-v2 coverage gain. No MIXED or
UNPROVEN row is promoted by this audit. A future finer-grained workflow
denominator requires a separately frozen constructor-to-workflow mapping and
must not reinterpret these source-file results.
