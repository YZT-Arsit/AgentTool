# Stage-7 Recovery Protocol

## Atomicity contract

One logical ORAM operation is committed when the trusted checkpoint atomically
names and authenticates the new copy-on-write server tree. Before that point,
restart returns the previous committed value. After that point, including loss
of the response acknowledgment, restart returns the new value. The protocol
does not merge partially written trees.

## Normal transaction

1. Serialize through the trusted coordinator and write a trusted PREPARED
   journal record with an opaque keyed target token.
2. Clone committed client state; read the old path into the stash.
3. Apply the logical read/write, remap the leaf, evict, and verify Path ORAM
   invariants.
4. Increment versions and write a complete authenticated tree under a new
   versioned filename.
5. Journal `server_written` with its authenticated root.
6. Atomically replace the signed client checkpoint, committing position map,
   stash, epoch, versions, root, and active filename together.
7. Journal `checkpoint_committed`, acknowledge, and delete the journal and old
   tree.

Files are written to a sibling temporary file, flushed with `fsync`, and
atomically replaced. Directory-entry durability and real-filesystem semantics
are not modeled beyond local `os.replace` behavior.

## Injected crash states

Crashes before path read, after path read, after stash update, after logical
mutation, after remap, during eviction, and after the server write all recover
the old committed checkpoint. A crash after client checkpoint but before
acknowledgment recovers the completed operation. All 32 architecture/crash-point
combinations recovered the expected value and passed ORAM invariants.

The test suite additionally terminates a child process after server write,
starts a new process, and observes the prior committed value.

## Restart and recovery

Recovery loads the runtime key and verifies the trusted checkpoint, reads every
physical bucket in the active tree, verifies the root and every envelope,
reconstructs tree/position-map/stash/version state, then runs uniqueness,
presence, position-map, and stash invariants. Unreferenced copy-on-write trees
and an uncommitted journal are discarded.

The recovery request is a full physical scan and never asks storage for a
logical record. It therefore hides the recovered logical identity in this
model, while revealing that recovery occurred, the ORAM domain, and tree size.

## Checkpoint and recovery measurements

| Architecture | Domains | Checkpoint bytes | Recovery read bytes | Recovery latency |
|---|---:|---:|---:|---:|
| Fixed canonical modular | 3 | 4,414 | 68,790 | 6.54 ms |
| Unified ORAM | 1 | 6,212 | 100,911 | 5.66 ms |
| Hybrid-P | 2 | 3,399 | 50,934 | 4.28 ms |
| Hybrid-PH | 1 | 1,699 | 25,405 | 2.04 ms |

These are small local domains and full-tree copy-on-write checkpoints. They
validate state transitions, not production scaling.

## Hybrid recovery

Restored caches are marked invalid. Hybrid-P revalidates authoritative
permission state before authorization. Hybrid-PH also synchronizes disclosure
history from its stored version before a history-dependent decision. If the
authority cannot establish current permission freshness, the result is DEFER.

The measured stale-restore cases required one RTT/74 bytes for Hybrid-P and two
RTTs/212 bytes for Hybrid-PH. Both rejected a formerly cached ALLOW after the
authority advanced to DENY; Hybrid-PH also recovered Device A's unseen event.

