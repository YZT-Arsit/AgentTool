# Gateway effect/recovery audit V6

All 23 current Go tests pass, including fixed frames, opaque client inputs,
late-result continuation, journal reopening, duplicate IDs, provider failures,
and fail-closed ring saturation. Raw output is
`results_v6/gateway_effect_tests_v2.txt`.

- `READ_ONLY`: PASS; prepared operations may safely retry.
- `IDEMPOTENT_EFFECT`: PASS only when the provider honors the operation-ID
  idempotency contract; committed results survive journal reopen.
- `NON_IDEMPOTENT_EFFECT`: PARTIAL. After an ambiguous crash/failure the journal
  fails closed and requires provider-specific reconciliation. V6 does not claim
  exactly once for such providers.
- Late results: the Pacer unit test confirms an older-session result can use a
  later already-existing public slot without extending the schedule.
- Gateway process restart: OPEN. Durable effect state exists, but no complete
  durable transport-session resumption test was run.
- Ring saturation: PASS fail-closed/no overwrite at the queue primitive. The
  live full-session saturation/recovery path was not run.

The one live V6 development arm executed all 50 effects exactly once and had
zero dummy heavy operations, but only 43 results reached the trusted consumer
within the public lifetime. It therefore fails the action-delivery functional
gate and cannot support a privacy claim.
