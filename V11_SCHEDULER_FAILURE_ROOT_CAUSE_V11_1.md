# V11 scheduler failure root cause

## Preserved negative result

The V11 development failure remains immutable at
`results_v11_development/functional_completion_run2/raw/multi-1/canonical_session/go_canonical_result.json`.
That session admitted one operation and invoked its provider once.  Its private
events reached `RESULT_COMMITTED` and `READY_PUBLISHED`, but the public result
array was empty.  The first Relay transaction spanned 737.5242 ms
(`response_observed_ns - request_observed_ns`), exceeding the frozen 555 ms
nominal session lifetime.  It is not relabelled as a pass.

## Code-level cause

The historical `common_action_gateway_v2/canonicalv9/runner.go` loop performed,
for each round, absolute waiting, OHTTP request creation, a synchronous
`clientHTTP.Do`, full response-body read, OHTTP decapsulation, and BHTTP decode
before advancing to the next round.  The Gateway also assigned the slot from an
arrival counter.  Thus one stalled stream prevented creation of every later
slot.  When the loop eventually advanced, its `remaining <= 0` branch skipped
the wait for all expired deadlines and emitted them back-to-back.

The defect classification is exactly:

```text
BLOCKING_ROUND_DEPENDENCY
+
CATCH_UP_BURST_AFTER_OVERRUN
```

This is an implementation/liveness defect, not a privacy holdout result.  No
V10 or V10.1 selected case was executed while diagnosing it.
