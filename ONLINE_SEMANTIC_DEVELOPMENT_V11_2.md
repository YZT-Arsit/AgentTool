# Online semantic development V11.2

| case | framework | passed | projection_equal | causal | public_sessions |
| --- | --- | --- | --- | --- | --- |
| TOOL_TO_TOOL | OpenAI Agents SDK | True | True | True | 1 |
| TOOL_TO_AGENT_AS_TOOL | OpenAI Agents SDK | True | True | True | 1 |
| TOOL_TO_HANDOFF | OpenAI Agents SDK | True | True | True | 1 |
| MICROSOFT_TOOL_TO_AGENT_AS_TOOL | Microsoft Agent Framework | True | True | True | 1 |
| OPENAI_AGENT_AS_TOOL_TO_TOOL | OpenAI Agents SDK | True | True | True | 1 |
| MICROSOFT_AGENT_AS_TOOL_TO_TOOL | Microsoft Agent Framework | True | True | True | 1 |
| OPENAI_TOOL_3 | OpenAI Agents SDK | True | True | True | 1 |
| MICROSOFT_TOOL_3 | Microsoft Agent Framework | True | True | True | 1 |

Level-A native/canonical causal trajectory equality: **8/8**. Compared fields were ordered logical actions, arguments, provider-visible logical requests, effect counts, per-operation outcomes, intermediate results, and final framework state. Chain-of-thought was not inspected.
