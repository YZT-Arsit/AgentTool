# V10 confirmatory decision rules (frozen before execution)

Phase: **V10A freeze only**. No selected V10 case has been executed.

## Semantic cases

The future comparison contains only: selected logical action, arguments, provider-visible logical request, effect count, operation/outcome semantics, result, and final framework-visible result/state. Chain-of-thought, hidden model reasoning, and irrelevant framework scheduling are excluded.

Each frozen case receives exactly one status:

- `PASS`
- `NATIVE_REFERENCE_FAIL`
- `CANONICAL_FUNCTIONAL_FAIL`
- `SEMANTIC_MISMATCH`
- `ENVIRONMENT_FAILURE`

No case may be removed or replaced after V10B starts.

## Structural/size pairs

Both arms must first pass all functional gates. If either arm is invalid, the privacy result is `INVALID_FUNCTIONAL_PAIR`, never `PASS`.

For a valid pair, structural privacy requires exact equality of `StrictStructuralProjection(A)` and `StrictStructuralProjection(B)`. Size privacy independently requires exact equality of `StrictSizeProjection(A)` and `StrictSizeProjection(B)`. A classifier cannot override an exact inequality.

The accepted implementation is [canonical_v9_1/projection.py](/D:/projects/mediation_trace_validation/canonical_v9_1/projection.py), SHA-256 `4b1181261eb012e9554b69538e371a1f12bd8e4364024c10022160d5bd0e0655`.

Structural fields are the actual Relay-observed profile/suite sequences, endpoint classes, normalized connection count/reuse pattern, session association, round count/order, request/response length sequences, and scheduled public lifetime. Exact equality excludes actual timestamps and literal ephemeral port identifiers.

Timing is not analyzed: `TIMING_PRIVACY = OPEN / NOT TESTED`; `PACKET_LEVEL_TIMING = OPEN`.

`DELIVERY_LEDGER = PARTIAL` for arbitrary nontransactional framework callbacks. Normal no-crash cases are valid only when their functional gates pass.
