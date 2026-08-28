# IR-v1 corpus selection audit

## Immutable selection

The historical IR-v1 corpus remains **314 Python files** at the two pinned framework commits. This document does not add, remove, or relabel any file or behavior. The exact path-level census is `CORPUS_FILE_INCLUSION_AUDIT.csv`; the immutable membership digest is recorded in `IR_V1_BASELINE_MANIFEST.json`.

| Framework/root | Included | Purpose |
| --- | ---: | --- |
| OpenAI Agents SDK `examples/**` | 216 | Public framework examples |
| Microsoft Agent Framework `python/tests/samples/**` | 5 | Materialized sample tests |
| Microsoft Agent Framework `python/packages/core/tests/**` | 93 | Core behavioral tests used because the pinned checkout materialized only a small sample subtree |
| **Total** | **314** | — |

## Discovery and exclusion

The candidate universe for this static Python AST audit is every materialized `.py` file in the two pinned local checkouts. It is not every non-Python repository file and not files omitted from a sparse checkout.

| Framework | Discovered | Included | Excluded |
| --- | ---: | ---: | ---: |
| OpenAI Agents SDK | 920 | 216 | 704 |
| Microsoft Agent Framework | 179 | 98 | 81 |
| **Total** | **1,099** | **314** | **785** |

| Exclusion reason | Files |
| --- | ---: |
| Framework implementation outside the selected example/behavior corpus | 388 |
| OpenAI framework tests outside the selected example corpus | 342 |
| Other materialized Python paths outside frozen roots | 55 |

Every excluded path and its reason appears in the machine-readable census.

## Parser, import, workflow, duplicate, generated, and vendor audit

- Parser failures among included files: **0**.
- Import failures: **not a selection gate**. The corpus extractor parses source with `ast.parse` and does not import modules; importability therefore was not measured or silently counted as success.
- Files with at least one detected workflow constructor: **25**.
- Workflow-only files (workflow constructor detected, no Agent constructor detected): **21**, all in the Microsoft corpus. They remain included because the frozen corpus intentionally covers framework-native workflows as well as Agent objects.
- Included files with no detected Agent constructor: **184**. These can still contribute Tool, workflow, state, middleware, branch, loop, or other behavior instances; inclusion was root-based rather than conditioned on a positive Agent detector.
- Exact-content duplicate groups: **3 groups / 19 files**. They are empty/package `__init__.py` files (16 OpenAI files in two groups, 3 Microsoft files in one group), not duplicated behavior-bearing programs. They remain in the immutable file count.
- Generated/vendor files: **none identified by path or provenance within the included roots**. Framework implementation and third-party code outside the roots were excluded by the path rules above.

## Version boundary

IR-v1 static lowering coverage remains `3574/7386 = 48.39%`. Any IR-v2 measurement must evaluate the identical 314 paths and separately report both static lowering and executable semantic support. A broader future corpus requires a new corpus/version identifier.
