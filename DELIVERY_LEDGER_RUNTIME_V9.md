
# DeliveryLedger Runtime V9

- First valid decoded result: delivered once and durably marked.
- Replay after durable delivery: suppressed; no second framework-visible callback.
- Restart after decapsulation and before callback: state reloads as deliverable and is delivered.
- Crash after callback but before durable delivered commit: **PARTIAL / application ambiguity**. The ledger cannot know whether the external callback completed; replay is possible.

This is deduplication and recovery behavior, not a general exactly-once theorem.
