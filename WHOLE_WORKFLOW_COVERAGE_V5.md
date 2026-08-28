# Whole-workflow coverage V5

The exact frozen 314-file corpus and conservative source-file workflow unit are
unchanged. V5 promotes no source file without a new source-traceable whole-file
semantic result.

| Status | Units | Fraction |
| --- | ---: | ---: |
| Fully executable | 33 | 21.85% |
| Partially executable | 97 | 64.24% |
| Unsupported | 21 | 13.91% |
| Total workflow units | 151 | 100% |

The other 163 of 314 corpus files are not workflow-bearing under the frozen
constructor rule. IR-v1 remains **3,574/7,386 = 48.39%** and is not replaced by
this metric. Row-level evidence is `WHOLE_WORKFLOW_COVERAGE_V5.csv`.

The 1,904 MIXED/UNPROVEN instances remain unsupported: 65 bounded after
normalization, 149 bounded under explicit framework contracts, 247
control-relevant dynamic, 13 genuinely arbitrary Python/runtime, and 1,430
extractor-ambiguous. No data-only instance was established with enough evidence
to assign that class, so its count is zero. These are triage labels, not support.
