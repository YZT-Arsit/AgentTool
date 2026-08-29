# V11.1 session failure semantics

The runner returns one explicit status:

- `COMPLETE`: every frozen slot was submitted, transport checks passed, and
  every admitted operation was returned.
- `SESSION_SCHEDULE_FAILURE`: at least one public launch exceeded tolerance.
- `SESSION_TRANSPORT_FAILURE`: a configured stream was not submitted or its
  HTTP/OHTTP/BHTTP validation failed.
- `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT`: the fixed public schedule
  ended with an admitted operation not delivered.

The final audit compares admitted operation IDs, the durable effect journal,
durable ready queue, response results, and DeliveryLedger-facing output.  A
committed/ready but undelivered operation is listed in
`pending_operation_ids`; accepted sessions require that list to be empty and
`silent_committed_result_losses` to equal zero.

No status extends the session, adds a private-dependent slot, reconnects, or
retries a selected evaluation.  Durable recovery evidence is preserved on a
failure.
