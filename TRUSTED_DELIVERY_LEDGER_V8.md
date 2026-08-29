# Trusted Delivery Ledger — V8

Status: **PARTIAL**

`action_privacy_v8.delivery.DeliveryLedger` is a durable trusted-side ledger keyed by `operation_id`. Its states are:

1. `RECEIVED_ENCRYPTED_RESULT`
2. `DECAPSULATED`
3. `FRAMEWORK_DELIVERED`

The ledger persists each transition atomically before returning. A replay at or after `FRAMEWORK_DELIVERED` is suppressed, while a crash before the framework callback leaves the result deliverable after restart. Python tests cover replay suppression and restart-before-delivery recovery.

There is an irreducible boundary ambiguity if the framework callback succeeds and the trusted process crashes before durably recording `FRAMEWORK_DELIVERED`. Exactly-once delivery is claimed only when that callback is itself idempotent or transactional. Otherwise at-least-once recovery plus duplicate suppression before the callback is the exact guarantee.

The implementation is not wired through a canonical RFC 9458 end-to-end path because that path is blocked, hence PARTIAL rather than PASS.

