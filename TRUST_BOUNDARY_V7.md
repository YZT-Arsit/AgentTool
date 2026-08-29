# Trust Boundary V7

## Trusted abstraction

The current `LocalTrustedBackend` is a software development boundary. The
intended trusted module owns private capability selection, official SimplePIR
client/recovery state, authenticated AgentDescriptor plaintext, the trusted
ActionRouteMap, protected action intent, authenticated OHTTP Gateway public key
configuration, and per-request OHTTP response contexts.

The trusted external Action Gateway owns OHTTP private keys, inner BHTTP
decoding, route-handle resolution, provider authorization, provider adapters,
effect/result journal, ready queue, and response encapsulation.

## Untrusted/local infrastructure

The local Relay owns no Gateway private key and can inspect only public profile,
endpoints, connection identity, body lengths, and performance timestamps. It
forwards opaque bodies exactly. The official SimplePIR server receives the
separately audited PIR transcript. A deterministic local provider learns its
own invocation and result.

## Current non-claims

Hardware attestation, malicious-hypervisor confidentiality, rollback
protection, microarchitectural privacy, prompt/LLM confidentiality, provider
privacy from the provider itself, packet-level timing privacy, and global
traffic analysis are not established. `HARDWARE_TEE = NOT_TESTED`.

The custom AES-GCM wire is a legacy development dependency, not part of the
canonical standards trust argument.

