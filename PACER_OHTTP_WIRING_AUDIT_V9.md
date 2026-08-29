
# PreparedSlot/OHTTP Wiring Audit V9

Status: **PASS as an engineering wiring invariant; timing privacy remains OPEN**.

Before the preparation boundary the Gateway reserves an eligible durable result, publishes it to the bounded V8 memory queue, snapshots it, RFC9292-encodes, RFC9458-encapsulates with the current round's response context, checks exact length, and constructs immutable `PreparedSlot`.

After the boundary the audited path is exactly:

1. wait/HTTP handler release scheduling;
2. `PreparedSlot.Send`;
3. one fixed-size `writer.Write`;
4. byte-count validation;
5. non-blocking in-memory acknowledgement.

Durable acknowledgement occurs asynchronously after send. No BHTTP, HPKE/OHTTP, JSON, provider call, or fsync occurs inside `PreparedSlot.Send`. This phase did not validate real packet timing.
