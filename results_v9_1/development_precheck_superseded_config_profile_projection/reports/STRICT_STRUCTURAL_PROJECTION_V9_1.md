
# STRICT Structural Projection V9.1

`StrictStructuralProjection(trace)` contains only: profile ID; public OHTTP key
ID/KEM/KDF/AEAD/config epoch; Relay and Gateway endpoint classes; public session
count; normalized connection counts and reuse pattern; connection policy; round
count/order; actual Relay-observed request/response length sequences; and the
scheduled public lifetime.

Raw send/receive timestamps and literal ephemeral TCP identifiers are excluded.
Connection identifiers are first-seen-normalized, so reconnects remain visible
while different source ports in independent executions do not cause a false
structural mismatch. Private labels and correctness events are never inputs.
