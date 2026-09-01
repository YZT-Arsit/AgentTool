# V12 Relay timing projection ordering closure

Base aborted evidence: `63bdd948dc5364cf3bdfa85bcc5170f5c5d5712b`. Historical protocol: `3dde92221b274148f4926de4d4df07d8a6c64cd5`.

## Verdict

The abort was caused by a projection-contract defect, not public transcript corruption. The old projection sorted Relay events by `request_observed_ns` and then required the public slot IDs in that order to be `1..R`. The runtime does not guarantee this: public HTTP/2 slots are independent, handler entry supplies the receive timestamp, response completion controls record append order, and exported events are structurally sorted by public slot.

The corrected integrity gate requires one complete public slot set, fixed sizes, valid application timestamps, one session, and one profile. It accepts observer-visible arrival reordering and preserves it in a fixed-width feature representation.

## Corrected representation

- `slot_indexed_session_relative_request_ns[R]`
- `chronological_request_inter_arrival_ns[R-1]`
- `slot_indexed_session_relative_response_send_ns[R]`
- `chronological_response_send_inter_arrival_ns[R-1]`
- `slot_paired_request_response_ns[R]`
- `total_session_span_ns`

An explicit arrival-rank vector is not added because it is mechanically derivable from the slot-indexed request timestamps. All request/response pairing remains by public slot. For P10, raw widths are `506,505,506,505,506`, producing a constant 2,589-element feature vector including the frozen summary features and total span.

## Unlabeled structural validation

The audit read only COMPLETE status/path metadata and raw public Relay events. It did not read protected labels, tasks, frameworks, partitions, old projections, or class-conditioned summaries.

- 2,258/2,258 prior COMPLETE sessions: exactly 506 events and slot set `1..506`.
- Duplicates, missing slots, and wrong slots: 0.
- Prior COMPLETE sessions with reordering: 0 (the old gate would not classify such a record COMPLETE).
- Valid request/response slot pairing: 2,258/2,258.
- Corrected projection and fixed-width vector: 2,258/2,258.

The original abort session has 506 events, a complete slot set, fixed 1,079/800-byte sizes, complete `response_send_ns`, complete public transcript, no liveness failure, no overflow, no pending result, and no silent result loss. Its only ordering discrepancy is that slot 4 was observed at `1788263441534531444 ns`, 77,630 ns before slot 3 at `1788263441534609074 ns`. The corrected projection passes.

Registry remains strict: the single cover thread performs queries synchronously through a query lock, and the bridge emits/records each response before incrementing ordinal.

## Closure status

Statistical protocol V3 passes and changes only Relay projection/feature semantics. All protected runtime paths are unchanged. Relevant deterministic tests pass 35/35. New protected sessions, classifier training, protected AUC, and protected bootstrap executions are all zero. The prior 5,040 planned identities remain permanent development exclusions and the old sentinel remains permanently aborted.

This closes readiness only for a future fresh P10 sentinel. P10 full development is not ready, timing privacy remains inconclusive, and timing GO remains no.
