# V11B0.1 preflight hardening audit

## Scope and immutable denominator

This was a pre-execution-only phase. The accepted V11B0 commit is `e8597888c47a08a9aaf63a8815a84956aed8b5e7`. S1/S2/S3/S4 remain 32/12/12/9, the structural holdout remains 14 pairs, and the 158-unit plan is byte-identical to V11B0. No seed, universe, exclusion, manifest, case, trajectory, pair, or execution-order file changed.

## Cross-host integrity

Committed frozen text is checked by authoritative commit/path Git-blob binding, `git diff --quiet`, and a clean main working tree. New V11B0.1 text is bound by LF-canonicalized SHA-256. Binary verification remains exact-byte SHA-256. A synthetic Git regression accepted equivalent LF/CRLF checkouts and rejected a semantic mutation.

## Linux SimplePIR bridge and framework provenance

On the authorized Linux host, the bridge was built with `go version go1.26.5 linux/amd64` from bridge source SHA-256 `978abd59...` and a clean SimplePIR checkout at `e9020b...`. The actual resolver path is `pir_integration/simplepir_bridge/acv-simplepir-online`, binary SHA-256 `2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b`. The binary was copied back without execution and independently rehashed to the same value.

OpenAI (`a40ae980...`), Microsoft (`af461de...`), and SimplePIR (`e9020b...`) all reported zero tracked/untracked changes on the authorized host. Import-only checks resolved `agents` and `agent_framework` inside those pinned source trees; no Agent case ran.

## Functional and finalization hardening

Structural validity now compares exact accepted/result/trajectory operation-ID multisets, rejects duplicates, missing and unexpected IDs, requires empty unresolved/waiter/pending sets, and checks provider-visible logical requests where mechanically available. The final summarizer is a pure immutable-evidence reader. Campaign completion is exclusively written only after 158 ledger records, 14 pair verdicts, and the frozen summary exist.

## Claim boundary

No selected outcome was observed. No privacy GO is issued. Timing privacy and packet-level timing remain open; hardware TEE is not tested; source-body executable subset remains zero.
