# V11.1 public-slot scheduler

For the public profile, slot `k` has the immutable deadline
`T_k = T_0 + (k-1) * Delta`.  All 111 fixed-width OHTTP requests and their
independent response contexts are prepared before `T0`.  At a deadline the
scheduler only starts the already-prepared request on an HTTP/2 stream and
continues; response reads, decapsulation, BHTTP validation, and DeliveryLedger
work occur outside that loop.

A late request is never transmitted as catch-up traffic.  If launch slip is
greater than the public development tolerance, the slot is recorded as a
schedule miss and is not submitted.  The session then ends as
`SESSION_SCHEDULE_FAILURE`.  It cannot be reported as a functional or privacy
pass.

The per-slot records preserve deadline, actual submit time, launch slip, and
miss status.  These are engineering diagnostics only.  V11.1 makes no timing-
privacy or packet-emission guarantee.

The trusted action plan is not provider-executed during release.  Provider
completion can only publish private ready state.  It cannot create a slot,
wake the scheduler, extend the slot table, or trigger a direct public send.
