# TrustedActionModule V6

`TrustedActionModule` owns capability mapping, PIR client state, selected Agent
ID, descriptor recovery, descriptor plaintext, cache state, route handle,
Gateway keys, and ActionCell construction. `LocalTrustedBackend` implements
this contract for local functional work only.

The bootstrap wrapper reuses the V5 X25519/HKDF challenge-bound session code and
derives separate descriptor and Gateway domains. It reports hardware
attestation as `NOT_TESTED`. Keys are generated at runtime; none are hardcoded
in canonical source or emitted into public traces. Rollback resistance needs a
future non-rollbackable platform or enterprise freshness anchor.

The future TEE backend must implement the same interface. Neither pinned Agent
framework, LLM inference, Tool implementation, IR compiler/interpreter, corpus
analysis, nor classifier enters this runtime TCB.

The trusted capability index is an exact ID map. On the 100,000-entry synthetic
catalog its encoded key/value payload estimate was 2,388,890 bytes. Keyword
search and cryptographic PSI are not part of V6; `CRYPTOGRAPHIC_PSI =
NOT_REQUIRED` for this resident-catalog configuration.
