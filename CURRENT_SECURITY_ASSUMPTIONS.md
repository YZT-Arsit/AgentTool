# Current Security Assumptions

1. The Privacy Kernel and CommonActionGateway Worker/Pacer are trusted and do
   not collude with `O_registry` or `O_agentcloud`.
2. The pinned official SimplePIR construction is used with fresh client
   randomness and its stated single-server assumptions; empirical classifiers
   are not its cryptographic proof.
3. Capsule rows fit the fixed 1,024-byte ABI. Unsupported/native code is rejected
   rather than executed in U.
4. The trusted encoder and Gateway share an ephemeral AEAD key through a
   restricted local file; U never receives it. AES-GCM nonce uniqueness is
   required.
5. Public protocol metadata is authenticated as AAD. Session/profile/direction
   and monotonic slot checks are enforced by endpoints.
6. The public PIR, control, and I/O profiles—including horizon, width, cadence,
   tunnel lifetime, and public outcome class—are selected before private work.
7. Cover control/I/O slots do no heavy work. Dummy PIR slots are genuine
   fresh-randomness queries to reserved rows.
8. `O_agentcloud` sees one common Gateway destination. Independently observed
   downstream provider traffic is not part of this observer.
9. Providers see their own plaintext operation. Cross-provider and
   provider/Gateway collusion are excluded.
10. Effectful providers are operation-ID idempotent for the guarantees claimed.
    Ambiguous non-idempotent provider outcomes are not called exactly-once.
11. Timing indistinguishability is conditional on a verified Linux isolated
    pacing boundary and a fresh frozen confirmatory run. This assumption is not
    validated on the current Windows host.
12. Microarchitectural/cache/power leakage, global Internet observation,
    provider GPU telemetry, arbitrary human delay, and TCP packet-level release
    timing are excluded.

