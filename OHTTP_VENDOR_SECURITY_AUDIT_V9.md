# OHTTP Vendor Security Audit — V9

Status: **AUDITED WITH EXPLICIT WRAPPER MITIGATIONS**

The vendored module is `github.com/chris-wood/ohttp-go`, recorded as
`SOURCE_TREE_HASH_ONLY` in `OHTTP_VENDOR_PROVENANCE_V9.json`. The source came
from the official commit-addressed GitHub codeload archive, but no completed
Git object fetch was available to independently prove the named commit.

The source implements `PublicConfig`, `PrivateConfig`, KEM/key configuration,
multiple advertised KDF/AEAD suites, request encapsulation, Gateway request
decapsulation, response encapsulation, client response decapsulation, and RFC
9292 known-length Binary HTTP. The V9 adapter calls these APIs and does not
modify HPKE or AEAD primitives.

## Findings and boundaries

- The pinned client selects the first advertised KDF/AEAD suite. V9 therefore
  binds one explicit public selected suite and checks it against the first
  authenticated Gateway configuration suite.
- The upstream Gateway checks key ID and algorithm validity, but does not by
  itself reject every valid yet unadvertised KDF/AEAD before cryptographic
  processing. V9 validates the seven-byte public request suite header first.
- `UnmarshalEncapsulatedResponse` accepts an opaque byte string, and the pinned
  client can slice a too-short response. V9 checks the minimum response length
  and converts any malformed-input panic to a fail-closed error.
- Per-slot request/response contexts are wrapped with one-use atomic guards.
  Wrong-slot, reused, modified, truncated, and unconfigured-suite tests pass.
- Upstream `TestVectorVerify` skips when vector files are absent. This is not
  counted as Appendix A conformance.

No review here upgrades a source audit into a formal cryptographic proof.

