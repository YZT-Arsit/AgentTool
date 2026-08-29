# Trusted online control protocol V11.2

The development IPC is framed JSON over the online runner's inherited stdin/stdout. It is local trusted-control traffic and never traverses the Relay.

- Runner to caller: `SESSION_READY`, `ACTION_ACCEPTED`, `ACTION_ADMITTED`, `ACTION_REJECTED`, `RESULT_AVAILABLE`, `SESSION_COMPLETE`, `SESSION_FAILURE`.
- Caller to runner: `SUBMIT_RESOLVED_ACTION` only.
- Every action carries one bounded operation ID and one resolved private action. Duplicate IDs, unknown routes, effect/policy mismatches, and capacity violations fail closed.
- `RESULT_AVAILABLE` is emitted immediately after current-slot OHTTP response decapsulation, not after round 111.
- A session failure wakes trusted waiters through an explicit failure event. No automatic action retry or second public session exists.

This IPC is a local software trust-boundary prototype, not hardware-attested communication.
