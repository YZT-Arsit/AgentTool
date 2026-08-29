# V11.1 current security matrix

| Property | Status | Evidence boundary |
|---|---|---|
| Blocking round dependency | REMOVED | independent slot goroutines and delayed-stream test |
| Catch-up burst | REMOVED | expired/missed slots are not submitted |
| Public preconnect | PASS | ordered setup events before T0 |
| HTTP/2 single-connection multiplexing | PASS | Relay-observed HTTP/2 and one connection per hop |
| Inner/outer slot binding | PASS | RFC 9292 bound fields under RFC 9458 |
| Per-slot OHTTP context | PASS | one-use slot-indexed contexts and out-of-order collector |
| Explicit session failure | PASS | four enumerated terminal statuses |
| Semantic regression | PASS | 38/38 |
| Structural regression | PASS | 11/11 |
| Multi-action | PASS | 5/5 |
| Timing privacy | OPEN / NOT TESTED | launch slip is diagnostic only |
| Packet-level timing | OPEN | no kernel/NIC claim |
| Hardware TEE | NOT_TESTED | LocalTrustedBackend only |
