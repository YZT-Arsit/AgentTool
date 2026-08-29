# V11.4.1 stronger structural recomputation

Status: **12/12** accepted V11.4 structural-development pairs remain exactly equal under the stronger committed projection.

No workload was rerun. The analysis read 24 immutable `go_online_result.json` records from the V11.4 qualification host. Each raw event sequence was first required to be exactly authenticated public order `(session=1, round=1..356)`; wall-clock completion order and timestamps are not projection inputs.

Every accepted trace has exactly 356 session IDs equal to `1`, 356 client and Gateway HTTP versions equal to `HTTP/2.0`, 356 requests of 1079 bytes, and 356 responses of 800 bytes. `StrictSizeProjection` is byte-for-byte equal to both the Linux-frozen projection result and the previously stored V11.4 size projection for every arm.

No scheduler miss, overflow, dummy provider operation, or silent committed-result loss was observed in these accepted arms.
