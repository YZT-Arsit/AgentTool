# Gateway Recovery V7

The recovery mechanism is transport-independent and is preserved for
V7-OHTTP.

## Durable state

- Effect recovery journal: accepted operation, declared effect semantics,
  provider-started state, committed result, and framework-delivery state.
- Durable ready queue: committed results, reservation state, eligibility, and
  delivered state.
- Public profile/admission configuration: maximum real operations, continuation
  tail, terminal slots, and declared completion bound.

## Restart rules

- Crash before provider start: retry all declared effect classes.
- Crash after provider start: retry READ_ONLY and IDEMPOTENT_EFFECT; return an
  explicit ambiguous outcome for NON_IDEMPOTENT_EFFECT unless provider
  reconciliation exists.
- Crash after result commit: return/requeue the committed result without
  replaying the provider effect.
- Crash after public send but before delivery acknowledgement: replay is
  permitted; trusted framework delivery deduplicates by operation ID.
- A reservation that survives a crash is made eligible again.

## OHTTP binding

A replayed application result is encapsulated using the new/current public
slot's OHTTP response context. An old OHTTP response context is never recovered
or reused merely because the result originated in an older slot.

The Go V7 recovery/queue suite passed on the prior Linux gate. The new OHTTP
context rule is contract-tested locally, but end-to-end RFC-wire restart remains
`NOT_TESTED` until a backend is integrated.

