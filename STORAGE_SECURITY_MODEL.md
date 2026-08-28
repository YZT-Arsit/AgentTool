# Stage-7 Storage Security Model

## Scope and threat split

The Stage-1–6 confidentiality model is unchanged: the cloud planner is
untrusted, the mediator and its client-side ORAM state are trusted, persistent
enterprise state is authoritative, and the infrastructure/storage host is
honest-but-curious for confidentiality. The host observes physical store
operations but not trusted memory, plaintext, logical record identifiers, keys,
position maps, or stash contents.

Stage 7 separately injects active storage faults. Those tests evaluate detection
and recovery engineering; they do not silently upgrade the complete system to a
malicious-host cryptographic proof. Network destinations, tool-provider
malice, planner trajectory privacy, TEEs, and microarchitectural leakage remain
out of scope.

## Authenticated block abstraction

No standard AEAD package is installed in the local environment. The executable
prototype therefore uses the pre-existing Stage-6 confidentiality abstraction
and HMAC-SHA-256 integrity. This is an **integrity simulator, not production
AEAD**. Production code must replace it with a reviewed AEAD implementation.

Each physical bucket envelope authenticates:

- a domain separator;
- an opaque physical bucket slot;
- storage epoch and per-bucket version;
- the sealed payload, which internally contains logical block/value data; and
- an HMAC tag derived from a runtime-generated, domain-separated key.

The host-visible envelope does not expose logical IDs. Generic verification
errors do not report a bucket, policy value, credential, history identity, or
plaintext.

## Freshness and rollback

Per-bucket versions and a global epoch are stored in a signed trusted
checkpoint. The checkpoint also binds the active copy-on-write tree filename,
an authenticated root over all physical envelopes, transaction ID, position
map, stash, geometry, and version map. An old block, bucket, or entire server
tree therefore fails against the current trusted root/version state. Key
rotation generates a fresh runtime key, increments the epoch, re-encodes all
buckets, and makes the former tree fail verification.

This guarantee critically assumes the trusted checkpoint/key state cannot be
rolled back with the server. A production deployment needs a non-rollbackable
freshness anchor such as a durable trusted metadata service, hardware counter,
or equivalently protected quorum. AEAD alone is insufficient.

## Trusted state and key management

Keys are generated with `secrets.token_bytes` at runtime and written only to the
synthetic trusted test directory. No secret is hardcoded. Separate ORAM domains
receive independent keys; within a domain, labeled HMAC derivation separates
block authentication, checkpoint authentication, and trusted-root uses.
Fixed modular therefore has separate data, permission, and history keys;
Unified has one storage key; the hybrids retain separate keys for each
outsourced subset.

Trusted durable state comprises keys, epoch/transaction/version metadata,
position map, stash, authenticated checkpoint/root, and any pending journal.
Hybrid caches additionally retain server versions but are invalid on restore
until revalidated. Exact experimental sizes are in
`TRUSTED_STATE_INVENTORY.csv`.

## Detected faults and limitations

The local audit detected ciphertext/tag/version corruption, missing and
duplicated buckets, old block/bucket/tree replay, stale permission/history
snapshots, and pre-rotation tree replay. Detection is fail-closed. It does not
establish resistance to denial of service, key compromise, side channels,
rollback of the trusted freshness anchor, or cryptographic implementation bugs.

