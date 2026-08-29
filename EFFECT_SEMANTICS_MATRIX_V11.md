# Effect semantics matrix V11

Executed local development cases cover success, provider error, and bounded timeout for TOOL, AGENT_SERVICE/AGENT_AS_TOOL, and the READ_ONLY EXTERNAL_HTTP route. The frozen external HTTP route has no effectful variant. NON_IDEMPOTENT timeout is reported as `EFFECT_OUTCOME_UNKNOWN`, never as exactly-once success/failure.

| action_family | agent_service_subtype | effect_semantics | outcome_class | effect_count | native_canonical_projection_equal |
| --- | --- | --- | --- | --- | --- |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | READ_ONLY | SUCCESS | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | READ_ONLY | SUCCESS | 0 | True |
| AGENT_SERVICE | HANDOFF | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | SUCCESS | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | READ_ONLY | SUCCESS | 0 | True |
| TOOL |  | READ_ONLY | ERROR | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | READ_ONLY | ERROR | 0 | True |
| TOOL |  | READ_ONLY | BOUNDED_TIMEOUT | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | READ_ONLY | BOUNDED_TIMEOUT | 0 | True |
| TOOL |  | IDEMPOTENT_EFFECT | SUCCESS | 1 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | IDEMPOTENT_EFFECT | SUCCESS | 1 | True |
| TOOL |  | IDEMPOTENT_EFFECT | ERROR | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | IDEMPOTENT_EFFECT | ERROR | 0 | True |
| TOOL |  | IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | 1 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | 1 | True |
| TOOL |  | NON_IDEMPOTENT_EFFECT | SUCCESS | 1 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | NON_IDEMPOTENT_EFFECT | SUCCESS | 1 | True |
| TOOL |  | NON_IDEMPOTENT_EFFECT | ERROR | 0 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | NON_IDEMPOTENT_EFFECT | ERROR | 0 | True |
| TOOL |  | NON_IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | 1 | True |
| AGENT_SERVICE | AGENT_AS_TOOL | NON_IDEMPOTENT_EFFECT | BOUNDED_TIMEOUT | 1 | True |
| EXTERNAL_HTTP |  | READ_ONLY | SUCCESS | 0 | True |
| EXTERNAL_HTTP |  | READ_ONLY | ERROR | 0 | True |
| EXTERNAL_HTTP |  | READ_ONLY | BOUNDED_TIMEOUT | 0 | True |
