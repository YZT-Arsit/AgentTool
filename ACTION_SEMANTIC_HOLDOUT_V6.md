# Fresh action-semantic holdout V6

The manifest and source hashes were frozen before execution at
`ACTION_SEMANTIC_HOLDOUT_V6_FREEZE.json` with digest
`c6e3ee67184c1b013c808fad6961c4ae0d71a73b4e0959cda7710060bb39c449`.
It excludes the prior V3 holdout sources and contains 16 cases: eight per
framework across read-only Tool, effectful Tool, Agent-as-service, and external
API action strata.

Result: **16/16 exact projection matches** on the one permitted run. Native and
mediated paths matched selected action, arguments, result, effect count,
operation ID, and outcome; dummy heavy operations were zero.

The V6 path in this holdout includes descriptor AEAD recovery and ActionCell
encryption/decryption before a deterministic local Gateway/provider adapter.
It is an outbound-action seam holdout, not a full live framework reasoning run
and not evidence for timing or malicious-host confidentiality.
