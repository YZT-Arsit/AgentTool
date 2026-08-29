
# Canonical Recovery Report V9

Gateway/client recovery rows meeting their predeclared expected outcome: **24/24**. One row is intentionally **PARTIAL**: framework callback after durable decapsulation but before durable `FRAMEWORK_DELIVERED`; replay may occur after restart.

READ_ONLY and IDEMPOTENT_EFFECT recover as executable before an outcome is committed and return committed results afterward. NON_IDEMPOTENT_EFFECT returns `EFFECT_OUTCOME_UNKNOWN` after provider start until a result is durably committed. Committed or in-flight results are replayable from the live journal/ready queue after restart. Arbitrary provider exactly-once is not claimed.

Executable call graph: `canonicalv9.Run -> gatewayHandler -> accept -> EffectRecoveryJournal.Accept -> EffectRecoveryJournal.Recover`. `RETURN_COMMITTED_RESULT` republishes to `DurableReadyQueue`; `EFFECT_OUTCOME_UNKNOWN` commits an ambiguous result without a provider call; `EXECUTE` durably marks provider start and invokes the local provider asynchronously. Provider completion calls `EffectRecoveryJournal.Commit -> DurableReadyQueue.Enqueue`; response preparation calls `ReserveEligible -> MemoryDeliveryQueue.PublishDurable/SnapshotEligible -> PreparedSlot.Send`; asynchronous acknowledgement calls `MarkDelivered` on both durable objects.
