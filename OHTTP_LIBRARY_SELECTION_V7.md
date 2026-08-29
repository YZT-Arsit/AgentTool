# OHTTP Library Selection V7

## Decision

`RFC9458_OHTTP_WIRE = NOT_IMPLEMENTED_OFFLINE`.

The local repository, `C:\Users\hasee\go\pkg\mod`, the Go module download
cache, repository-local toolchain/dependency directories, the local pip cache,
and the active Python environment contain no RFC 9458 plus RFC 9292
implementation. Cargo and NuGet caches were absent. The authorized remote Linux
host was not auditable in this continuation because interactive authentication
was not available; it is not counted as a successful cache audit.

The standard-library `crypto/hpke` source is not sufficient: HPKE alone is not
OHTTP or BHTTP. No custom cryptography was implemented.

## Preferred completion dependency

The first integration candidate remains `github.com/chris-wood/ohttp-go`,
subject to an offline source/vendor review confirming:

- RFC 9458 request and response APIs;
- RFC 9292 known-length request and response encoding;
- Gateway key configuration parsing/serialization;
- fresh request contexts and correct response-context binding;
- Appendix A test-vector support;
- acceptable license and transitive dependency inventory.

No version, commit, or checksum is invented here. Those fields must be pinned
only after the source is actually acquired and audited. The exact unresolved
integration requirements are machine-readable in
`OHTTP_DEPENDENCY_MANIFEST_V7.json`.

## Implemented now

The checkout contains client/Gateway interfaces, key-configuration schema,
per-slot context contracts, fixed outer-profile validation, exact-byte opaque
Relay forwarding, application-layer late-result association, and fail-closed
backend gating. These are architecture contracts, not an RFC implementation.
