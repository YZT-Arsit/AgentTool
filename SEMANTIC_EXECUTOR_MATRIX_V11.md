# Semantic executor matrix V11

All **38/38** executed development rows produced equal independently generated native and canonical semantic projections. These are Level A action-boundary results, not untouched source-body execution.

| framework | action_family | agent_service_subtype | argument_schema | effect_semantics | outcome_class | native_canonical_projection_equal |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI Agents SDK | TOOL |  | ONE_STR | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_INT | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_BOOL | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | OPTIONAL_PRIMITIVE | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | TWO_PRIMITIVES | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | THREE_PRIMITIVES | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | BOUNDED_OBJECT | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | ONE_STR | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | ONE_INT | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | ONE_BOOL | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | OPTIONAL_PRIMITIVE | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | TWO_PRIMITIVES | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | THREE_PRIMITIVES | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | TOOL |  | BOUNDED_OBJECT | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | READ_ONLY | SUCCESS | True |
| Microsoft Agent Framework | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | AGENT_SERVICE | HANDOFF | AGENT_TASK | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | READ_ONLY | ERROR | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | READ_ONLY | ERROR | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | READ_ONLY | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | READ_ONLY | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | IDEMPOTENT_EFFECT | SUCCESS | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | IDEMPOTENT_EFFECT | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | IDEMPOTENT_EFFECT | ERROR | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | IDEMPOTENT_EFFECT | ERROR | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | NON_IDEMPOTENT_EFFECT | SUCCESS | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | NON_IDEMPOTENT_EFFECT | SUCCESS | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | NON_IDEMPOTENT_EFFECT | ERROR | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | NON_IDEMPOTENT_EFFECT | ERROR | True |
| OpenAI Agents SDK | TOOL |  | ONE_STR | NON_IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | AGENT_SERVICE | AGENT_AS_TOOL | AGENT_TASK | NON_IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | True |
| OpenAI Agents SDK | EXTERNAL_HTTP |  | ONE_STR | READ_ONLY | SUCCESS | True |
| OpenAI Agents SDK | EXTERNAL_HTTP |  | ONE_STR | READ_ONLY | ERROR | True |
| OpenAI Agents SDK | EXTERNAL_HTTP |  | ONE_STR | READ_ONLY | BOUNDED_TIMEOUT | True |
