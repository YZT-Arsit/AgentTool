# V11.4 public profile model

V11.4 qualifies, but does not redesign, the V11 online architecture. The public profile is `Gamma(M,H,Delta,B,D,T,...)`, selected before private execution. It defines `A=ceil(H/Delta)`, `C=ceil(B/Delta)`, `D=M`, and `R=A+C+M+T` for the current one-result-per-response architecture. The qualification fixes `M=50`, `B=50 ms`, and `T=1` after period selection.

The privacy-facing structural contract is parametric: the same `Gamma` produces the same session count, endpoint classes, HTTP/2 reuse policy, round count/order, OHTTP suite, and request/response size sequences. Private action count, identity, target, kind, causal depth, repetition, frequency, and placement do not create slots or extend the horizon. An action becoming ready after `H` is rejected with `PROFILE_ADMISSION_CLOSED`.

Qualification is sequential and predeclared. Stage P tests 10, 20, and 25 ms on a public 1,000 ms, one-operation, NOOP-heavy profile and freezes the first 500/500 candidate. Stage H then tests 2,000, 3,000, 4,000, 5,000, 7,500, and 10,000 ms in ascending order using the frozen period. No two-dimensional tuning or post-result candidate addition is permitted.

This is scheduler/transport reliability engineering, not a timing-privacy test. `TIMING_PRIVACY = OPEN / NOT TESTED`; packet-level timing remains open.
