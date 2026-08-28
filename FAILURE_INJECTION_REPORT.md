# Stage-7 Failure Injection Report

## Summary

All injected storage corruptions and replay attempts were detected and aborted;
all eight crash points recovered to the defined old-or-new atomicity boundary;
hybrid stale restores did not re-authorize revoked access; concurrent history
appends did not lose events; and the four required effect/log ambiguity cases
reconciled without duplicate effects.

## Storage integrity and rollback

For each of Fixed canonical modular, Unified ORAM, Hybrid-P, and Hybrid-PH, the
audit injected 11 cases: ciphertext, tag, and version corruption; missing and
duplicated bucket/block; old block, bucket, and tree snapshots; old permission
and disclosure snapshots; and pre-key-rotation replay. All 44 cases returned
`DETECTED` with a generic secret-independent error. These results rely on the
current trusted checkpoint/key not being rolled back.

## Crashes and service faults

All 32 architecture/crash-point combinations recovered correctly. Before the
checkpoint commit, the old value survived; after checkpoint but before
acknowledgment, the completed value survived. A real child-process termination
after server write also recovered the old committed value in a new process.

Local timeout, connection drop, delay, temporary unavailability, duplicate
response, and process termination were exercised across private-data,
permission, history, storage, and mock-tool roles. Authorization returned DEFER
when permission freshness could not be established. Duplicate tool requests
were idempotent.

## Recovery privacy and errors

Recovery scans physical tree slots and exposes no logical ID field. Tests reject
`block_id`, synthetic contact IDs, policy values, history identities, and bucket
locations in observer-facing traces/errors. Recovery nevertheless reveals its
occurrence, domain, and physical size, so the result is PARTIAL rather than a
claim of fully oblivious failure behavior.

## Interpretation

The results establish internal consistency for a small local feasibility
prototype. They do not test Byzantine coordinator faults, simultaneous rollback
of trusted and server state, distributed partitions, disk-controller failure,
production AEAD/KMS behavior, or a non-idempotent external tool. Detailed rows
are in `results_stage7/integrity_injection.csv`, `crash_injection.csv`,
`effect_atomicity.csv`, and `FAILURE_MATRIX.csv`.

