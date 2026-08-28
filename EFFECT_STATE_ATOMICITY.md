# Stage-7 Effect and State Atomicity

## Guarantee and protocol

The mock tool and authoritative disclosure log cannot share a true atomic
transaction. Stage 7 implements a recoverable saga:

1. assign a unique operation ID and durably journal `LOCAL_PREPARE`;
2. create an idempotent `PREPARED` audit record;
3. invoke the tool with the operation ID;
4. journal `EFFECT_CONFIRMED` when a result is known;
5. commit the audit record to a monotonically ordered version; and
6. journal `DONE`.

The tool durably binds each operation ID to a SHA-256 digest of its first
payload. Retrying the same ID/payload returns the previous result without
another effect; reusing the ID with a different payload fails closed.

## Ambiguous outcomes and reconciliation

On restart or timeout, reconciliation queries the tool by operation ID. If the
effect exists, it idempotently commits the audit entry. If it does not and the
audit entry is only PREPARED, it marks the entry ABORTED. A COMMITTED audit entry
without a tool effect is treated as an integrity failure rather than silently
accepted.

| Injected case | Effect count | Final audit state | Result |
|---|---:|---|---|
| Effect succeeds; log commit fails | 1 | COMMITTED after reconciliation | pass |
| Log prepare succeeds; effect fails | 0 | ABORTED | pass |
| Effect succeeds; crash before acknowledgment | 1 | COMMITTED after reconciliation | pass |
| Effect succeeds; ambiguous timeout | 1 | COMMITTED after reconciliation | pass |

No tested case produced a duplicate effect, permanent unaudited success, or
false committed audit entry.

## Limitations

The result is sound for the durable local mock interfaces. A real tool must
honor the same durable idempotency/query contract, and the enterprise audit
service must preserve ordered conditional updates. If a real tool neither
supports operation-ID idempotency nor authoritative outcome queries, the
mediator cannot generally distinguish an unobserved success from failure. That
is an external interface requirement, not something ORAM can repair.

