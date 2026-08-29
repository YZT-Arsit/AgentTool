# OHTTP Dependency Requirements

To enable the canonical backend, vendor an audited library that provides:

1. RFC 9458 client request encapsulation and response decapsulation;
2. RFC 9458 Gateway request decapsulation and response encapsulation;
3. RFC 9292 known-length request and response encoding/decoding;
4. authenticated Gateway Key Configuration support;
5. fresh per-request context and correct response-context binding;
6. Appendix A test-vector support or byte-exact equivalent hooks; and
7. a license and complete transitive dependency manifest suitable for local
   vendoring.

Record module path, exact version, source commit, archive/source SHA-256,
license, `go.sum` entries, and every transitive module before enabling it. Then
implement the existing `ClientBackend`, `GatewayBackend`, and
`KnownLengthBHTTPCodec` interfaces without changing cryptographic primitives.

No Internet download was performed in this task.

