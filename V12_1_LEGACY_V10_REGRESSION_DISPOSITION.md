# V12.1 legacy V10-H50 regression disposition

The retained historical failure was originally collapsed into a generic canonical response-size mismatch. New diagnostics used fresh DEV identities and did not overwrite that evidence.

- Windows, frozen V10-H50 static profile (111 rounds, 5 ms, 50 predeclared actions): 0/100 functional. Ninety-three sessions ended `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT`; seven exposed an actual Gateway HTTP 502 response with a 31-byte body. None was an RFC 9292 or RFC 9458 fixed-size encoder producing the wrong 800-byte success body.
- Frozen Linux development host, the same static profile and 100 fresh identities: 100/100 functional, zero schedule misses, and no transport diagnostics.

The exact cause is therefore synchronous durable filesystem latency and occasional local upstream timeout on the Windows execution path, amplified by the superseded 555 ms V10 public lifetime. It is not a deterministic OHTTP/BHTTP serialization defect. The code path is shared, so the generic append-only-WAL repair applies to both static and online runners; however, the V10 5 ms profile is not the V12 356-round/10 ms/H3000 profile and is not used for V12 confirmation.

Disposition: preserve the V10 test and negative Windows evidence. Do not xfail, skip, widen an assertion timeout, or reinterpret it as PASS. Current V12 qualification is decided on its frozen Linux execution environment and its own online profile. Timing privacy remains untested.
