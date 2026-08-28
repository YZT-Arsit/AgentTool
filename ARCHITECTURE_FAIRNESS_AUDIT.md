# Architecture Fairness Audit

## GAAP-derived

### Directly from the source

- A private-data database stores private user values under public keys.
- A permission database stores allow/deny decisions for private-data/external-
  party pairs and is queried before disclosure.
- A persistent disclosure log records each disclosure.
- For indirect/transitive flows, the disclosure log is queried to reconstruct
  private taints associated with an earlier external call.
- The trusted environment intercepts tool calls and enforces disclosure policy.

### Inferred

- A direct disclosure needs a private-data DB read; a disclosure of an already
  available API result need not reread that same private-data DB item.
- Permission checking precedes a successful disclosure-log write.
- These source-supported steps are sufficient for a local `SEND_MESSAGE` sink.

### Added only for simulation

- Synthetic values and a local mock send outcome.
- 1,024 private-data records, 1,024 permission records, and 2,048 log records.
- Path ORAM, Z=4, 4 KiB equal-size blocks, balanced/natural episode generators,
  and offline classifiers.
- Canonical dummy slots and the unified-address-space alternatives.

### Necessary deployment assumption

The three documented logical databases are separately addressable encrypted/
ORAM services whose endpoint identities are visible to the host. GAAP does not
claim this storage deployment and does not use ORAM in the cited paper. The
positive leakage result therefore validates a possible modular deployment of
GAAP's documented components, not GAAP's published implementation.

### Fairness assessment

**MIXED/HIGH source fidelity.** State components and semantic accesses are
documented; host-distinguishable ORAM deployment is added and decisive. Unified
and modular variants share identical Path-ORAM code, Z, block size, eviction,
and stash policy. Unified capacity equals the exact sum of modular capacities.

## PAuth-derived

### Directly from the source

- Each server derives an NL slice for an expected operation.
- Signed envelopes bind concrete server-returned values to symbolic provenance.
- Receiving servers verify values/provenance against their slices.
- Literal operands and derived operands can legitimately have different inline
  provenance, but authorization remains a server-local consistency check.

### Inferred

- A server may cache its derived slice for a task. The simulator models one
  `SLICE_STATE` lookup. This is not a paper-mandated persistent database.

### Added only for simulation

- A local `SHARE_FILE`-like mock action, synthetic operands, one 1,024-block
  slice store, Path ORAM deployment, and inline hash work representing envelope
  verification.
- Canonical/unified labels are retained only to run the mandatory comparison;
  with one store and fixed work they are structurally equivalent.

### Necessary deployment assumption

Only the assumed slice cache is ORAM-backed. Signed envelopes remain inline,
matching the source, and no provenance/history database is invented.

### Fairness assessment

**MIXED.** Slice/envelope semantics are documented, persistence is not. Because
the paper does not document multiple mediator stores, Stage 4 records PAuth as a
negative validation rather than forcing cross-store leakage.

## Cost fairness

Every ORAM uses the same functional Path-ORAM implementation, bucket size four,
greedy eviction, stash policy, and 4 KiB block. Modular tree heights are the
minimum needed for each declared store; unified height is the minimum needed for
the exact sum. No tree is deliberately oversized and no variant receives a
weaker ORAM algorithm. Raw logical accesses and transferred bytes are both
reported.
