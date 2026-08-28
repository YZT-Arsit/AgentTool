# Long-horizon functional root cause

## Preserved failure

`LONG-HORIZON-STRUCTURAL-V1-20260828` remains immutable: equal public shapes,
AUC 0.500, 32/96 heavy operations per class, zero delivered results, and no
workflow returns. It is not privacy evidence.

## First lost stage

Private logs show requests were accepted, Worker operations started, local model
responses completed, and successful results were written after durable journal
completion. The Pacer nevertheless emitted only `WAIT`. Source audit found the
first loss at result-ring consumption:

```go
if pending.Session < currentPublicSession {
    discard
}
```

Provider/journal work frequently completed after its original three-slot,
10 ms session. The Pacer treated such a result as expired instead of retaining
it for the next already-scheduled slot. This violated continuation semantics and
caused the kernel to remain pending.

## Repair

`common_action_gateway_v2/pacer.go` now treats a result as eligible when its
request session is less than or equal to the current public session. A future
session result stays queued. A late result never creates or delays a slot; it is
encrypted into the next pre-existing response slot. `canonical_v3/runner.py`
also consumes a private zero-I/O `RETURN` immediately after accepting a final
`DONE` result, avoiding a needless extra public session.

Go tests cover the continuation predicate. The existing live canonical Gateway
integration test passes after the repair.

## Development horizon sweep

| Profile | Public duration | Heavy ops | Results | Returned | Gate |
| --- | ---: | ---: | ---: | --- | --- |
| SHORT | 530 ms | 3/3 | 2/3 | no | FAIL |
| STANDARD | 1,550 ms | 3/3 | 3/3 | yes | PASS |
| LONG | 2,720 ms | 3/3 | 3/3 | yes | PASS |

All profiles used 1,024-byte frames, eight public sessions, three slots per
session, and zero dummy heavy operations. Exact delivery slots and measured
Worker latency are in `LONG_HORIZON_DEVELOPMENT_RESULTS.csv`.

This is development evidence for one `MODEL -> TOOL -> MODEL -> RETURN`
workflow. It does not close all V5 workflows and does not authorize a new
privacy holdout or timing claim.
