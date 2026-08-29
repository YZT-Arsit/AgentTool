# Agent-Service Effect Semantics V8

V8 replaces the V7 implicit READ_ONLY assumption with an authenticated
`AgentServiceRouteDescriptor` containing route handle, effect semantics,
policy ID, and placement.

`TrustedActionRouter` returns the descriptor's exact declaration for:

- `READ_ONLY`
- `IDEMPOTENT_EFFECT`
- `NON_IDEMPOTENT_EFFECT`

Parameterized tests pass for all three. A non-idempotent Agent service is never
rewritten to READ_ONLY. The recovery policy remains: READ_ONLY may retry;
IDEMPOTENT_EFFECT may retry only under the provider's operation-ID contract;
NON_IDEMPOTENT_EFFECT after an ambiguous start returns `OUTCOME_UNKNOWN` unless
provider reconciliation exists.

Status: `AGENT_SERVICE_EFFECT_SEMANTICS = PASS` at the authenticated routing and
recovery-policy layer. Canonical OHTTP end-to-end execution is blocked.

