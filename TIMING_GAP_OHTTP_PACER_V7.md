# Timing Gap: OHTTP and Pacer V7

RFC 9458 protects encapsulated HTTP contents and separates Relay knowledge from
Gateway plaintext. It does not claim traffic-analysis resistance. RFC 9292
padding can normalize message size; it does not make release times independent
of secrets.

The V7 `FixedSlotScheduler` specification fixes nominal message count, order,
lifetime, and deadlines. The existing userspace Pacer is an
application/socket-boundary mechanism and has prior negative timing evidence;
it is not lower-layer packet-transmit enforcement. Pacer-style isolated
lower-layer shaping remains future work.

OHTTP integration must not awaken, extend, or reschedule public slots on result
readiness. Even after integration, an observer-boundary timing experiment on a
fresh holdout is required.

```text
TIMING_PRIVACY = NOT_TESTED
PACKET_LEVEL_TIMING = OPEN
TIMING_GO = FORBIDDEN
```

