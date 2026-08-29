
# Canonical Runner V9 TCB

Canonical orchestration/control source: **1435 physical LoC** across the six V9 runner/diagnostic files. This count excludes the local provider emulator, frozen corpus tooling, experiments, reports, SimplePIR implementation, and vendored OHTTP dependency.

Trusted local client domain: SimplePIR client recovery, descriptor key/codec, router, OHTTP client contexts, and DeliveryLedger. Trusted Gateway domain: OHTTP private key/configuration, BHTTP decode, private route map, effect journal, provider orchestration, ready publication, and response preparation. The Relay sees only final OHTTP bytes and public profile/HTTP metadata. Providers are local deterministic test processes.

Pinned cryptographic dependencies remain those in the standards freeze: official SimplePIR commit recorded in metrics and `third_party/ohttp-go` with source-tree-hash-only provenance. This phase adds no primitive and makes no hardware-attestation claim.
