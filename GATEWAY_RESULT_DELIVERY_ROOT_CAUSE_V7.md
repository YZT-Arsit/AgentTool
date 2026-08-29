# Gateway Result Delivery Root Cause V7

## Frozen evidence

This audit reads the immutable V6 run at
`results_v6/gateway/structural/agent_identity/a` and does not modify it.
The run admitted and executed **50** real operations. The trusted
module received **43** results; **7**
were not delivered.

## First failed lifecycle boundary

The first uncompleted lifecycle transition is:

```text
durably committed result / result-ring publication
    ->
pacer observation in a pre-existing public response slot
```

All 50 worker operations reached completion, durable `COMMITTED` journal state,
and the worker's result writer drained its completion channel. The frozen worker
summary reports zero result-ring waits. The seven missing operation IDs never
appear in the pacer's private delivery log or the trusted-module delivery list.

The last public response frame was sent at monotonic timestamp
`1787905591332487200`. Exactly **43** operations completed by
that boundary. The seven missing operations completed **28.976 ms to
307.515 ms after** the public schedule had ended.

## Root cause

**The V6 public profile admitted work without reserving enough public
continuation capacity for the declared provider-completion bound.** The worker
and public pacer were decoupled, but the result queue was transient and the
public session lifetime ended before late results became ready. The failure was
not a ciphertext, effect, or ring-overwrite failure; it was a public admission
and lifecycle-capacity error.

The V6 one-item pacer staging variable is also inadequate for robust recovery
and out-of-order completion, although it did not cause these seven losses: all
seven completed only after the final public response slot.

## Required V7 repair

V7 needs all of the following, as a single invariant:

1. a public admission bound and reserved continuation tail;
2. a bounded durable private ready queue, with idempotent operation IDs;
3. eligibility of a late result for any later pre-existing public slot;
4. explicit `PROFILE_OVERFLOW` when the public capacity proof is violated;
5. restart replay from durable journal/ready state with trusted-side duplicate
   suppression; and
6. a functional gate proving exact delivery for 1/10/50/100-operation runs
   before any privacy result is generated.

## Evidence limits

V6 did not timestamp the instant at which each result entered the shared-memory
ring. `result_ring_published=true` in the companion CSV is a source-and-summary
inference: the writer blocks until every completion is pushed, the channel is
closed only after all workers finish, `writerDone` is awaited, and the worker
summary was written with zero ring waits. V7 adds explicit lifecycle events so
future recovery claims do not depend on this inference.
