# V12 provider-completion bound semantics

The frozen V11.4/V12 public profile uses `B = 50 ms` to reserve
`C = ceil(B / Delta) = 5` continuation rounds. The capacity rule is
`R = A + C + M + T`. The authoritative invariant is therefore **result
readiness at the private ready queue no later than the declared completion
bound after admission**, not merely completion of application logic inside the
provider handler.

This interpretation follows the executable profile contract in
`common_action_gateway_v2/v7/profile.go`: its continuation proof assumes that
all operations "become ready at the declared completion bound" and reserves
only `C` rounds before result draining. `PUBLIC_PROFILE_MODEL_V11_4.md` and
`PROFILE_CAPACITY_PROOF_V11_4.md` bind the same `B` into the public slot count.
There is no independently declared public allowance for connection scheduling,
request transfer, handler scheduling, response writing, or response decoding.

Before V12-PROVIDER-CLOSURE, `canonicalv9.newEngine` also used the same 50 ms
value as `http.Client.Timeout`. That implementation measures the complete local
HTTP transaction. The `EARLY_READY=2 ms` and `LATE_READY_WITHIN_BOUND=30 ms`
development modes control private handler delay, but do not redefine the public
bound as handler-only computation.

Consequences:

- A handler whose logical computation finishes below 50 ms can still violate
  the frozen completion contract if its result is not decoded and ready by
  50 ms.
- Increasing only the HTTP timeout would permit result readiness beyond the
  capacity proof and is not an admissible reliability repair in this phase.
- A generic repair may reduce avoidable local transaction overhead or remove a
  runtime defect, provided the unchanged public schedule and 50 ms readiness
  bound remain authoritative.
- Diagnostic timestamps are private development evidence. They do not change
  OHTTP/BHTTP bytes, Relay events, structural projections, or the timing-privacy
  claim, which remains open.
