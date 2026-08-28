# Agent-as-Tool and effect-recovery audit

## Private Agent call stack

The IR/runtime now uses explicit private `CALL_AGENT` and `RETURN_AGENT` states.
A call frame contains the parent logical Agent, parent private context, private
Tool name, call ID, and canonical arguments. The child logical Agent is selected
as state and runs through the same physical `AgentControlExecutorV2`; no Agent-
specific process, endpoint, worker, or queue is created. Call depth is bounded
by a public program bound and fails closed on overflow.

Both existing framework forms are extracted without rewriting upstream logic:

- OpenAI Agents SDK's native `_is_agent_tool` / `_agent_instance` metadata.
- Microsoft Agent Framework's native `Agent.as_tool()` wrapper closure, whose
  captured Agent is matched by object identity against the compiled workload.

Focused development regression: 10/10 IR-v2 tests pass, including both native
Agent-as-Tool object forms. This is development evidence, not the untouched
holdout result.

## Effect classes and recovery

| Declared class | Retry after prepared/failed state | Claim |
| --- | --- | --- |
| `READ_ONLY` | Allowed; committed result may be cached | No external effect |
| `IDEMPOTENT_EFFECT` | Allowed with the identical operation ID | At-most-one provider effect only if the provider honors idempotency |
| `NON_IDEMPOTENT_EFFECT` | Not automatically retried after an ambiguous boundary | Fail closed; reconciliation required; no exactly-once claim |

The Worker durably writes `PREPARED` before dispatch and copy-on-write/fsyncs
`COMMITTED`, `RETRYABLE`, or `AMBIGUOUS_RECONCILIATION_REQUIRED` afterward.
Crash-point tests cover restart after durable prepare, retry of an idempotent
operation, restart after committed result, ambiguous timeout, and semantic reuse
of an operation ID. The Go package test suite passes.

## Limits

The local journal does not make an intrinsically non-idempotent remote provider
exactly once. It detects its own ambiguous state and blocks replay. Resolution
still needs a provider query/reconciliation API or human/manual recovery. The
journal is local durability engineering, not Byzantine or replicated storage.
