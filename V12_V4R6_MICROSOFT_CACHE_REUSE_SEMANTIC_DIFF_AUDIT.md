# V12 V4R6 Microsoft Cache-Reuse Semantic Diff Audit

This audit used only the immutable archive at base closure `0ff3bde2b9e889a0677c7b1b38f2bb3854f2eb6d`. The failed identity was not reexecuted. No session, classifier, AUC calculation, or runtime modification occurred.

## Exact semantic difference

The first difference is zero-based operation index 12 (the 13th operation), `opa380c470dbaf99c973ea69cbb967`.

| Field | Native | Canonical | Equal |
|---|---|---|---|
| operation ID | `opa380c470dbaf99c973ea69cbb967` | same | yes |
| logical action | `repeated_same_agent_cache_tool` | same | yes |
| arguments | `{"city":"Paris"}` | same | yes |
| causal parent | `ope7de65c400a475e2cfb223e1292d` | same | yes |
| provider request | `{"operation_id":"opa380c470dbaf99c973ea69cbb967","action_family":"TOOL","agent_service_subtype":null,"arguments":{"city":"Paris"}}` | same | yes |
| effect count | `0` | `0` | yes |
| outcome semantics | `READ_ONLY:SUCCESS` | `READ_ONLY:ERROR` | **no** |
| result | `V11_RESULT:d5e99e72df9116e2d1d48a58` | empty string | **no** |
| framework-visible intermediate result | deterministic result above | empty string | **no** |
| final framework state | `framework-completed:DYNAMIC_SEQUENCE` | same | yes |

All other 29 operations have matching deterministic results and outcome semantics. The operation-ID inventory is exactly 30/30, all 30 were delivered in the expected causal order, provider-visible requests and effect counts match, and the final framework state matches.

## Evidence-backed cause classification

For operation 12, the local provider recorded request receipt, successful decoding, and logical completion in 364,006 ns. The Go provider client recorded `PROVIDER_CONTEXT_DEADLINE_EXCEEDED` after 50,856,110 ns while awaiting headers. Its public result therefore had status 3 and null payload; the canonical adapter mapped that to `READ_ONLY:ERROR` and an empty result. The provider subsequently recorded `BrokenPipeError` while writing the response.

The frozen native oracle evaluates the same SUCCESS/READ_ONLY case as `READ_ONLY:SUCCESS` with `V11_RESULT:d5e99e72df9116e2d1d48a58`. Accordingly, the classification is `SEMANTIC_RUNTIME_DEFECT`, not an oracle-comparison defect and not merely a framework presentation difference.

## Duplex repair smoke scope

Existing fresh V4R6 evidence covers the five proposed smoke coordinates: C1/OpenAI has passing cache-reuse and K=6 descriptor-transition units; T7/OpenAI and T7/Microsoft have passing Agent-as-Tool transition units; T9/OpenAI and T9/Microsoft each have passing early- and late-readiness units. Every cited unit has exact semantic results plus complete Registry, Relay, duplex projection, and response-clock checks.

Therefore `SMOKE_SCOPE_FUNCTIONAL_ELIGIBILITY = PASS`, while `FULL_P10_FUNCTIONAL_ELIGIBILITY = FAIL`. Because the observed failure is in the shared provider execution path, the additional no-common-runtime-defect condition is not met: `READY_FOR_DEVELOPMENT_DUPLEX_REPAIR_SMOKE = NO`, `READY_FOR_FULL_P10_SENTINEL = NO`, and `READY_FOR_CONFIRMATORY = NO`.
