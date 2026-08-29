# Registry Security Definition — V8

## Observer and secret

The untrusted registry/PIR server observes public database parameters, preprocessing state, opaque query/answer bytes, sizes, and timing. The secret is the selected Agent row/ID.

## Mechanism and trusted state

The official pinned SimplePIR construction provides single-server query privacy under its stated assumptions. Query generation, client hint/state, randomness, answer recovery, descriptor authentication, expected-ID checking, and descriptor plaintext belong to the trusted module. The server stores encrypted 1024-byte `AgentDescriptorV7` rows.

The server trace must contain no Agent ID/name, route handle, descriptor plaintext/hash, or secret-derived file offset. Repeated queries require fresh randomness.

## Scope

This game says nothing about Relay observations, destination privacy after lookup, action semantics, or timing/resource side channels. The V8 1K/10K/100K runs establish correctness and integration sanity; the cryptographic privacy claim derives from the pinned SimplePIR construction, not a classifier.

