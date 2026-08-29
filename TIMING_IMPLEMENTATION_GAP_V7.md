# Timing Implementation Gap V7

This task measures protocol/runtime behavior only. It does not implement
stealth networking or claim resistance to host monitoring.

RFC 9458 protects encapsulated HTTP contents and separates Relay knowledge from
Gateway plaintext; traffic analysis remains possible. RFC 9292 padding can
normalize sizes but does not enforce release timing. The public-profile model
defines nominal round period, response lag, round count, and lifetime. Future
local runs may record scheduled/actual timestamps and scheduler deviation as
performance data.

The existing userspace Pacer is an application/socket-boundary prototype with
known earlier negative timing evidence. It is not packet-level enforcement and
this task does not modify the kernel, qdisc, NIC, or security products.

```text
TIMING_PRIVACY = NOT_TESTED
PACKET_LEVEL_TIMING = OPEN
```

Pacer and NetShaper remain design comparisons only; no equivalence to their
lower-layer guarantees is claimed.

