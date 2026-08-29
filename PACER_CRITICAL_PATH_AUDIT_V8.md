# Pacer Critical-Path Audit — V8

Timing privacy remains **OPEN / NOT TESTED**.

## Legacy V7 live path

The V7 pacer performs queue reservation and delivery marking through a durable JSON queue. Depending on the transition, the path can include a variable scan, serialization, file creation/write, `fsync`, rename, frame construction, socket write, and another durable state update. This is retained as frozen legacy evidence and is not a clean deadline path.

## V8 refactor

`common_action_gateway_v2/v8/memory_delivery.go` moves durable publication out of the final send step. Before the deadline, the pacer snapshots a bounded in-memory queue and constructs an immutable fixed-size `PreparedSlot`.

Operations remaining between `preparation_cutoff` and public send invocation:

1. wait on the already selected public deadline;
2. call `PreparedSlot.Send`;
3. one fixed-size `io.Writer.Write` invocation;
4. validate returned byte count;
5. attempt a non-blocking in-memory acknowledgement enqueue.

No JSON encoding, file write, `fsync`, rename, provider call, retry, result parsing, or durable delivered-state mutation occurs in `PreparedSlot.Send`. The acknowledgement consumer may persist later; a crash before that persistence permits replay, handled by the trusted delivery ledger.

Evidence is compile/vet only because Application Control blocked execution of the generated V8 test binary. The refactor is not wired into a canonical OHTTP command, so this is an engineering audit—not a timing-security result.

