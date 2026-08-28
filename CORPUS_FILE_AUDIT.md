# Frozen-corpus file inclusion audit

## Why 314 files entered IR-v1

IR-v1 did not scan every Python file materialized in the two checkouts. It selected three predeclared corpus roots at pinned commits:

| Framework/root | Included `.py` files | Rationale |
| --- | ---: | --- |
| OpenAI Agents SDK `examples/**` | 216 | Public framework examples were the selected OpenAI behavior corpus. |
| Microsoft Agent Framework `python/tests/samples/**` | 5 | Materialized sample tests in the pinned sparse checkout. |
| Microsoft Agent Framework `python/packages/core/tests/**` | 93 | Core behavioral tests were included because this pinned checkout materialized only a small sample subtree. |
| **Total** | **314** | Exact paths are frozen in `CORPUS_MANIFEST.csv`. |

All 314 files parsed without syntax errors. They contain 1,043,639 OpenAI bytes and 3,963,658 Microsoft bytes. File count and byte count are descriptive only; neither weights semantic importance.

## Complete materialized-file census

The audit discovered every materialized `.py` file under both pinned checkout roots, excluding only Git metadata from discovery. The complete **1,099-row** census is `CORPUS_FILE_INCLUSION_AUDIT.csv`; each row states framework, commit, relative path, size, inclusion, rule, and exclusion reason.

| Framework | Discovered materialized `.py` | Included | Excluded |
| --- | ---: | ---: | ---: |
| OpenAI Agents SDK | 920 | 216 | 704 |
| Microsoft Agent Framework | 179 | 98 | 81 |
| **Total** | **1,099** | **314** | **785** |

| Exclusion reason | Count |
| --- | ---: |
| Framework implementation, not selected example corpus | 388 |
| OpenAI framework tests outside selected example corpus | 342 |
| Other path outside frozen IR-v1 corpus roots | 55 |
| **Total** | **785** |

This is a materialized-checkout audit, not a claim that the sparse checkouts contain every upstream file. Files absent from the pinned local checkout cannot be enumerated as discovered files. The commit identifiers and selected roots are therefore part of the corpus definition.

## Inclusion invariant

The set of `included_ir_v1=YES` rows is checked for exact equality with all 314 `(framework, relative_path)` entries in `CORPUS_MANIFEST.csv`. Future IR-v2 evaluation must use this same set and the same commits. Adding newly discovered examples, removing detector artifacts, or changing root selection requires a separately named corpus/version and cannot replace the IR-v1 baseline.
