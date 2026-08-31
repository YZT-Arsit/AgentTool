# V12 non-timing baseline evidence audit

The executable dependency path for B0-B3 is unchanged from the phase base commit. Historical results therefore remain **B0 1/14, B1 2/14, B2 11/14, B3 13/14**. B4/B5 final evidence is `DEFERRED_TIMING_PROFILE`; no final values were manufactured in this phase.

The authoritative local 100K SimplePIR evidence remains present and hash-bound, with 10/10 correct fresh queries. Its evidence directory is absent from the new Linux test bundle, which caused four Python audit-test failures and is reported as an environment-completeness defect rather than silently calling those tests PASS.
