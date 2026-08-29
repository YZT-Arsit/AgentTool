# OHTTP Dependency Status V7

## Engineering status

`RFC9458_IMPLEMENTATION = NOT_AVAILABLE_OFFLINE`.

The repository, Go module and download caches, repository toolchains, pip cache,
and active Python environment contain no compatible RFC 9458 plus RFC 9292
implementation. Local Cargo and NuGet caches are absent. The Go standard
library's HPKE source is not an OHTTP/BHTTP implementation and was not wrapped
in a custom protocol.

The canonical interfaces remain disabled and return explicit unavailable
errors. The custom AES-GCM protocol remains `LEGACY_DEV_TRANSPORT` and cannot
satisfy the canonical backend gate.

## Dependency required later

The preferred candidate is `github.com/chris-wood/ohttp-go`, subject to source
review confirming RFC 9458 request/response handling, RFC 9292 known-length
messages, Gateway key configuration, Appendix A support, and acceptable
license/transitive dependencies. Its version, commit, checksum, and license
must be recorded from the acquired source; none is invented offline.

See `OHTTP_DEPENDENCY_MANIFEST_V7.json` and
`OHTTP_LIBRARY_SELECTION_V7.md` for the exact completion gates.

