# V12 timing admission clock root-cause audit

## Decision

`CLOCK_MISMATCH_CONFIRMED = YES`, but `EFFECTIVE_CLOCK_REPLAY_50_OF_50 = NO` (46/50). Per the frozen phase rule, runtime implementation stops here. No scheduler, pacer, admission, delivery, PIR, profile, or horizon source was changed; no fresh workload or timing attack was run.

The required disposition is `H3000_CAPACITY_STILL_INSUFFICIENT`. The mismatch is a real design defect, but it is not sufficient to repair the immutable 46/50 trace.

## Mechanical source finding

`common_action_gateway_v2/canonicalv9/online.go` constructs nominal `deadline` and `cutoff = deadline - lead`. The preparation worker rejects/skips using nominal cutoff (lines 294 and 307), the scheduler commits using nominal cutoff (line 405), and `engine.deliveryCutoffs` is populated from nominal cutoff (line 224; consumed by `runner.go` lines 606-612). Only after commitment does dispatch compute `eligible = max(deadline, previousDispatch + period)` (lines 414-417).

Thus the old action commitment clock is nominal while the public emission clock is effective/no-burst. The worker can permanently advance past a nominally expired slot while that slot's effective cutoff is still in the future. Result eligibility has the same nominal/effective inconsistency.

## Clock alignment and conservative replay

Python `SESSION_T0` was recorded at 3566354114073860 ns. Go recorded `T0_ASSIGNED` at 119771743 ns relative to its process clock. Because Python records `SESSION_T0` only after receiving `SESSION_READY` and starting the PIR cover thread, 3566353994302117 ns is an upper bound on the Go process-clock origin. Using that upper bound makes every private arrival *earlier* than it could really have been, deliberately favouring the proposed repair.

The last nominal admission cutoff (slot 300) was 3517.685091 ms; its effective cutoff would have been 3543.653121 ms. Operation 47's descriptor was available no earlier than 3840.726615 ms: 297.073494 ms after even the last effective cutoff.

The round-290 public result dispatch for operation 46 occurred at 3443.755324 ms. Framework delivery occurred no earlier than 3813.583191 ms, a lower-bound delay of 369.827867 ms. The next intent followed 27.059924 ms later. This delay, not PIR exhaustion, placed operation 47 beyond all 300 admission-capable slots.

## Operations 47-50

- operation 47 `op7317990911e13f1ec0f093a397f1`: intent 3840.643115 ms, descriptor ready 3840.726615 ms, framework delay 27.059924 ms, cache delay 0.0835 ms, effective replay: not admitted.
- operation 48 `opb668676f1fe16227517abfc65066`: intent 3862.272233 ms, descriptor ready 3862.350594 ms, framework delay not available (prior operation was rejected), cache delay 0.078361 ms, effective replay: not admitted.
- operation 49 `op5249c879daa4ce316efd428a04d8`: intent 3876.861139 ms, descriptor ready 3876.933791 ms, framework delay not available (prior operation was rejected), cache delay 0.072652 ms, effective replay: not admitted.
- operation 50 `op3e706dbfd138bca425bbe3ed4915`: intent 3890.820859 ms, descriptor ready 3890.891146 ms, framework delay not available (prior operation was rejected), cache delay 0.070287 ms, effective replay: not admitted.

At operation 47 arrival, slots 287-300 were already past their effective commitment cutoffs; they classify `EFFECTIVE_SLOT_ALREADY_COMMITTED`. Operations 48-50 arrived after operation 47 had exhausted the fixed 300-slot admission set. No skipped slot for these four operations was available solely because the old nominal cutoff was used.

Across the complete trace, skipped-slot classifications and all 50 reconstructed operation records are frozen in the JSON companion. The effective-clock greedy replay admits 46/50, not 50/50.

The complete trace contains 42 skipped slots in class A, 204 in class B, and 8 in class D. Thus the nominal clock did discard 42 opportunities prematurely elsewhere in the trace, but restoring them counterfactually still does not make operations 47-50 available before the fixed admission set ends.

## Preserved boundaries

- `DEV-MDCC-OA-SAME-AGENT-DEPTH50-001` remains FAIL and was never retried.
- `K6 / PIR60 / EPOCH6000 / Q100` is not changed here; the failed trace used one real PIR, 99 dummy PIR queries, and 49 authenticated descriptor cache hits.
- The prior PIR proof is not promoted to an integrated action-capacity PASS because H3000 fails this replay.
- Timing privacy remains inconclusive; timing GO remains NO; packet-level timing remains open.
- No V12 universe, seed, selected manifest, authorization, result root, live capacity identity, or timing-attack identity was created.
