# Online reliability stress V11.2

| gate | passed | total |
| --- | --- | --- |
| TOOL_1 | 100 | 100 |
| TOOL_TO_TOOL | 50 | 50 |
| TOOL_TO_AGENT_AS_TOOL | 50 | 50 |
| TOOL_TO_HANDOFF | 50 | 50 |
| MICROSOFT_TOOL_TO_AGENT_AS_TOOL | 50 | 50 |
| DYNAMIC_5_ACTION | 30 | 30 |
| DYNAMIC_10_ACTION | 20 | 20 |
| INTERNAL_EXTERNAL_MIX | 30 | 30 |

Campaign D: **380/380**. Same-final-configuration pre-freeze check: **17/20**, with 3 explicit `PROFILE_ADMISSION_CLOSED` failures before the tenth causal action. The reproducible reliability gate is therefore **FAIL**. Aggregate Campaign D dummy heavy operations=0, profile overflow=0, schedule misses=0, silent committed-result loss=0.
