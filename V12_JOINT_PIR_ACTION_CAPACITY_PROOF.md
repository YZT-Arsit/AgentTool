# Joint PIR/action capacity proof

Status: **PASS for the frozen capacity contract; not a timing-profile GO**.

For `H=3000 ms`, `K=6`, PIR period `P=60 ms`, enforced PIR completion bound `B=50 ms`, and action-preparation margin `L=1 ms`, the latest public arrival for a new descriptor is:

`A = H - K*P - B - L = 2589 ms`.

Even when a K-sized burst arrives immediately after a cover opportunity, the Kth real query starts strictly before `A + K*P`, completes strictly before `H-L`, and leaves the preparation margin before H. A cache miss at or after A fails closed as `PIR_REAL_RESOLUTION_ADMISSION_CLOSED`; a cached same-Agent action continues under the ordinary action admission rule. A PIR call exceeding 50 ms fails closed rather than silently consuming an unbounded service interval.

Depth-50 same-Agent causality needs one real descriptor resolution and 49 trusted cache hits. Distinct-Agent transitions are bounded by K=6. This proof does not predeclare future actions and does not change H.

The subsequent live campaign did not invalidate this mathematical PIR/action proof, but it stopped on a separate Microsoft native-framework depth limit before that workload reached canonical/PIR execution.
