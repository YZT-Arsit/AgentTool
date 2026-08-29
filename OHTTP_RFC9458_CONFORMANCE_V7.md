# OHTTP RFC 9458 Conformance V7

## Status

`OHTTP_RFC_CONFORMANCE = NOT_TESTED`.

No compatible RFC 9458 implementation exists in the accessible offline
dependency set, so neither RFC 9458 Appendix A nor RFC 9292 wire conformance was
executed. Passing the local contract tests does not establish RFC compliance.

## Frozen future gate

Before status may change, a pinned implementation must pass:

1. authenticated Gateway key-configuration parsing;
2. complete Appendix A request/response example where exposed by the library;
3. fresh request context per public slot;
4. response decapsulation only with the corresponding slot context;
5. known-length BHTTP request and response round trips;
6. exact final Encapsulated Request and Response size assertions after HPKE
   overhead, not merely plaintext padding;
7. wrong key/configuration, corrupt request, corrupt response, replay/duplicate,
   stale session/slot, and context-mismatch rejection; and
8. an opaque Relay byte-for-byte forwarding test around actual OHTTP bytes.

The existing custom AES-GCM tests are excluded from this conformance gate.

