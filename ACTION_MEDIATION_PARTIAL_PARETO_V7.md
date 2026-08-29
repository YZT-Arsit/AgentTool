# Action Mediation PARTIAL Pareto V7

This is a decomposition of the frozen 473 V6 `PARTIAL` instances. No
instance is relabeled, and no hypothetical coverage is counted.

| Family | Instances | Files | OpenAI | Microsoft | V7 status |
|---|---:|---:|---:|---:|---|
| MCP_INVOCATION_OR_APPROVAL | 184 | 13 | 6 | 178 | PARTIAL |
| MCP_RESULT_CONTENT_OR_HELPER | 117 | 7 | 0 | 117 | PARTIAL |
| MCP_SERVER_DISCOVERY_OR_SKILL_CATALOG | 92 | 19 | 30 | 62 | PARTIAL |
| MCP_OTHER_UNPROVEN | 75 | 15 | 19 | 56 | PARTIAL |
| HOSTED_PROVIDER_MCP | 5 | 4 | 5 | 0 | PARTIAL |

## Interpretation

The Pareto is dominated by MCP-related source sites, but the frozen corpus
mixes actual invocation/approval seams, hosted-provider activation, discovery,
content conversion, and helper code. A small generic hook may cover the first
category; it cannot honestly cover the others without framework-contract and
runtime semantic tests. V7 therefore preserves all 473 as PARTIAL.

The exact source-traceable examples and required lowering contracts are in the CSV.
