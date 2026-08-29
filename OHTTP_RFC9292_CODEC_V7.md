# RFC 9292 Binary HTTP Codec V7

## Status

`RFC9292_BHTTP = PARTIAL`.

Implemented components:

- fixed private request schema for protocol version, action kind, route handle,
  operation ID, protected arguments, continuation, and authorization;
- fixed private response schema contract;
- one inner semantic target,
  `https://action-gateway.invalid/v1/agent-slot`;
- validation that NOOP contains no real route or arguments; and
- a `KnownLengthBHTTPCodec` interface with an unavailable implementation that
  fails closed.

Not implemented offline:

- RFC 9292 field-section and known-length message wire encoding;
- byte-level request/response round trips;
- padding calculation against actual BHTTP and OHTTP/HPKE overhead; and
- exact final Encapsulated Request/Response length validation.

No private ad-hoc serializer is called BHTTP. A standards implementation must
fill the interface before this status can become PASS.

