# V12 non-timing dependency audit

This audit was frozen before decisive non-timing tests. Classification follows
the executed code/data path, not a test's conceptual label or later outcome.

## Non-timing independent

The independent boundary contains private routed-name construction and native
framework projection; provider diagnostic/result classification; effect WAL,
READY recovery, replay suppression and DeliveryLedger binding; the prebuilt
SimplePIR query process; OHTTP/BHTTP codec and authentication; route and
capability authorization; static timestamp-erased projections; corpus/sample
classification; and non-executing manifest/integrity guards.

`OnlineSimplePIRResolver` is separable from the public scheduler when tested as
its own prebuilt process. `CanonicalOnlineSession` is not: its present success
condition includes the hard-deadline public session, so live canonical semantic
tests are timing-platform dependent even when their semantic projection omits
timestamps.

## Timing profile dependent

Exact `Delta`, `R`, admission/completion/drain rounds, public lifetime, profile
identifier, hard-deadline miss semantics, final B4/B5 runs, and profile
qualification depend on the unresolved final timing profile.

## Timing platform dependent

Cadence reliability, launch-slip distributions, deadline crossings, complete
online canonical sessions, timing classifiers, socket timing, and packet timing
depend on a qualified execution platform. They are excluded from the
non-timing gates before outcomes are observed.

The historical `REDEFINE_STRUCTURAL_TRANSCRIPT` review is preserved but not
implemented. Timing remains a core claim with status `OPEN / NOT TESTED`.

