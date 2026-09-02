# V12 Duplex Repair Smoke Sentinel Closure

The smoke campaign hard-stopped on the predeclared common-integrity gate after
14 of 640 identities: 13 complete sessions, one failed session, and zero
retries. The collection was hash-closed. No classifier, AUC, bootstrap,
randomization test, or class-conditioned timing statistic was run.

The failed immutable identity is
`DEV-TAD-P10-T7-OA-SENTINEL-B30001-C0` at execution ordinal 13. Its Gateway
recorded 506 response-release opportunities, but opportunity 1 had a release
deadline miss and the Relay application observer received only 505 of the 506
required slots. Slot 1 was absent; no duplicate slot was present. The runtime
reported `SESSION_TRANSPORT_FAILURE`. The exact underlying cause is not
established here.

This is a public-transcript/application-observability integrity failure, so
the smoke dataset is not statistically evaluable. The smoke verdict is
`NOT_EVALUABLE_COMMON_INTEGRITY_ABORT`, not PASS or timing-distinguishability
FAIL. All 640 frozen smoke identities are permanent development exclusions.
P10 full, P20, P25, confirmatory timing, and final holdout were not run.
