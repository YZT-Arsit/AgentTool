# Effect recovery V5 report

The durable journal and local provider tests pass after the continuation repair.

| Effect class | Recovery result |
| --- | --- |
| READ_ONLY | PASS: prepared work can retry with the same operation ID. |
| IDEMPOTENT_EFFECT | PASS under a provider idempotency contract; committed result is durable. |
| NON_IDEMPOTENT_EFFECT | PARTIAL: ambiguous send/effect boundaries fail closed and require reconciliation. |

Crash tests cover prepared restart, timeout before effect, effect-before-timeout,
durable commit before result-ring publication, commit before delivery, and
duplicate operation IDs. Late results use subsequent pre-existing slots; they
do not extend the public schedule.

The system does not claim exactly once for a provider without an idempotency or
query/reconciliation contract. The journal is local copy-on-write/fsync storage,
not Byzantine or replicated durability.
