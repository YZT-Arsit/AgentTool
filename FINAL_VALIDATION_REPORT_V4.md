# Final validation report V4

## Executive outcome

**METHOD FREEZE NOT YET JUSTIFIED.** The implementation work closed two
development gaps—private Agent-as-Tool call/return and explicit durable effect
recovery semantics—but the requested confirmatory evidence did not close:

1. the new 20-case untouched semantic holdout is incomplete because 12 cases
   were invalidated by harness defects and were correctly not rerun;
2. the frozen eight-family long-horizon transport traces were equal, but their
   whole-workflow functional gate failed (zero delivered results and no returns);
3. timing privacy was intentionally not tested in this environment.

No negative or partial result was removed or converted into a pass.

## Frozen result preservation

- IR-v1 behavior baseline: **3,574/7,386 = 48.39%**, unchanged.
- IR-v1 unsupported denominator: **3,812**, unchanged.
- IR-v2 72/72, including Tool 18/18: **development regression only**.
- A versioned post-change rerun of those same development strata remains 72/72;
  it is preserved in `SEMANTIC_FIDELITY_V2_DEVELOPMENT_REGRESSION_20260828.csv`.
- Frozen corpus: 314 paths at the existing pinned OpenAI/Microsoft commits.
- Materialized-checkout census: 1,099 Python files = 314 included + 785
  excluded, with every exclusion reason retained in
  `CORPUS_FILE_INCLUSION_AUDIT.csv`.

## Whole-workflow executable coverage

The distinct conservative source-file workflow denominator contains 151 units:

| Status | Units | Fraction |
| --- | ---: | ---: |
| Fully executable | 33 | 21.85% |
| Partially executable | 97 | 64.24% |
| Unsupported | 21 | 13.91% |

This does not replace the 48.39% behavior-instance metric. The zero fully
executable Microsoft source-file units are preserved as a negative consequence
of large test files combining Agent behavior with unresolved persistence,
middleware, sessions, and workflow constructs.

## MIXED/UNPROVEN decomposition

All 1,904 rows remain unsupported. Triage found 65 source-traceable bounded,
149 framework-contract-bounded, 260 genuinely dynamic, and 1,430 extractor-
ambiguous instances. These values are not projected coverage. Agent-as-Tool is
the clearest bounded Pareto family; state/memory ambiguity dominates the open
set. Exact family/source/framework evidence is in
`MIXED_UNPROVEN_DECOMPOSITION_V2.md` and its CSV.

## Agent-as-Tool development result

`CALL_AGENT`/`RETURN_AGENT` now use a bounded private call stack and preserve
one public physical executor. The compiler recognizes both OpenAI metadata and
Microsoft's captured native Agent wrapper. Focused development tests pass for
both. Because all four Agent-as-Tool holdout cases were harness-invalid, this
feature is **development-validated, confirmatory-open**.

## Effect recovery

Gateway effect handling is no longer a boolean in-memory promise. Provider
configuration declares `READ_ONLY`, `IDEMPOTENT_EFFECT`, or
`NON_IDEMPOTENT_EFFECT`; a durable copy-on-write/fsync journal records prepare
and completion state. Restart tests pass. Ambiguous non-idempotent work fails
closed and requires reconciliation. Exactly-once is claimed only under a real
provider idempotency contract; it is not claimed for arbitrary providers.

## Untouched semantic holdout

The frozen 20-case manifest was run once without tuning. Eight cases validly
passed. Twelve cases failed in the evaluation harness before semantic
comparison (illegal generated Tool schema or unresolved actor aliases). They
remain raw failures and are classified `HARNESS_INVALID`, not semantic passes or
semantic mismatches. The holdout therefore yields **no aggregate fidelity
estimate**.

## Long-horizon structural/size privacy

The experiment was frozen before execution across eight requested leakage
families and repeated-observation windows 1/2/4/8/16/32. All emitted transport
projections were exactly equal and both grouped classifiers produced AUC 0.500
at every aggregation window. However, the frozen three-slot cadence expired
before journal-hardened results were delivered: each class executed only 32 of
96 intended heavy operations, delivered zero results, and never returned. Thus
only first-operation transport-shape equality is supported; long-horizon
whole-workflow privacy remains open. Timing confirmation was not attempted.

## Runtime TCB

The measured online project TCB is 22 files, 2,905 physical LoC and about 2,579
nonblank/non-comment LoC:

- trusted control substrate: 7 files / 976 approximate code LoC;
- trusted Gateway enforcement: 15 files / 1,603 approximate code LoC.

Compiler (259), corpus tooling (1,065), provider emulator (168), experimental
analysis (1,122), and untrusted cloud-plane code (308) are reported separately.
This supports a bounded trusted control substrate claim—not a fully trusted
Agent runtime—but the Gateway remains a significant TCB component.

## Verification

- Focused Python validation: **26 passed, 1 deselected**.
- Gateway Go packages: **PASS**.
- Broad Python run with a repository-local temporary directory: **164 passed,
  1 skipped**. The skip was the explicitly disabled canonical integration; the
  frozen long-horizon run was executed separately and retained its functional
  failure.

## Strongest current falsification findings

1. A pre-frozen holdout is not useful unless the generic executor/harness is
   itself preflighted without consuming holdout cases.
2. Only 21.85% of conservative workflow source-file units are fully executable;
   the static extractor still cannot establish semantics for 1,430 MIXED rows.
3. The expanded privacy trace completed but failed its functional E2E gate, so
   its chance-level classifier values cannot support the whole-workflow claim.

## Required next step

Do not tune or rerun `SEMANTIC-HOLDOUT-V2-20260828`. Pretest a generic holdout
harness on development-only fixtures, then freeze a new set of previously unseen
official examples. Engineer a separately named development horizon that
accommodates durable journal latency, then freeze a new untouched long-horizon
experiment; do not retune or rerun the failed frozen profile. Only after both
semantic and E2E gates close should the method/security boundary be frozen.
Timing requires its own reference-platform confirmation later.
