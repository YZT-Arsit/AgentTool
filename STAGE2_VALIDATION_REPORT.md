# Stage-2 Validation Report

## 1. Executive conclusion

**STRONGLY SUPPORTED** within the controlled synthetic threat model.

A functional Path-ORAM implementation hid recipient identity and linkability,
while a private mediation-policy state remained perfectly distinguishable from
ordered store structure after exact matching on total accesses, per-store counts,
and read/write counts. Fixed-count padding (`V2-PAD`) and fixed-histogram padding
(`V2-HIST`) did not remove the sequence signal. V3 canonicalization returned
performance to chance/permutation levels with identical synthetic semantics.

## 2. Reviewer objection tested

The objection was that Stage 1 might show only an ordinary access-count channel.
Stage 2 therefore held the public action (`SEND_MESSAGE`) constant and created
three controls:

1. equal total accesses but different dependency-store composition;
2. equal total accesses and equal per-store counts but different order;
3. equal total accesses, per-store counts, and operation histograms, varying only
   the order induced by private mediation policy.

The strongest control is decisive in this simulator: count-only and histogram-
only features are at chance, while ordered stores classify the state perfectly.

## 3. Real Path ORAM implementation

`src/path_oram.py` implements a binary server tree, configurable bucket capacity
Z, client position map, stash, logical blocks, uniformly random leaves, complete
root-to-leaf reads, stash insertion, logical reads/writes, remapping after every
access, greedy deepest-to-root eviction, and implicit dummy capacity in every
fixed-size bucket transfer. The default experiment uses 128 logical blocks per
store, height 7, and Z=4.

The host-visible event contains only the public store/operation/order, old leaf,
physical bucket path, tree height, buckets touched, and fixed physical transfer
count. It contains no logical block ID, value, handle, private class, or dummy
indicator. Payload encryption is abstracted because content is not the measured
variable.

This is a **functional Path-ORAM implementation used to generate physical access
traces**, not production cryptographic storage. It omits authenticated encryption,
recursive position-map ORAM, constant-time client code, concurrency, crash
recovery, and network/system side channels.

Automated tests cover latest-value reads, exactly-once block presence, complete
position maps, bucket capacity, assigned-leaf path compatibility, deterministic
replay, and non-stable remapping. A discovered initialization bucket-overflow bug
was fixed before any reported experiment was accepted.

## 4. Realistic mediation workload

All 9,000 primary episodes (3,000 for each seed 0, 1, and 2) are synthetic
`SEND_MESSAGE` actions. Each uses a recipient, attachment, sender/account,
recipient/attachment/sender policies, credential, disclosure history read, and
audit write. Sixteen recipients, 32 documents, and four accounts are sampled;
values use reserved forms such as `example.invalid`.

The hidden class is a private policy-evaluation mode:

- **just-in-time validation:** resolve each object and immediately check its
  corresponding policy;
- **batch-safe validation:** collect required objects/credential, then evaluate
  the same policy records.

Both modes are plausible mediator strategies for identical authorized output.
The policy mode necessarily selects the schedule in this experimental semantics;
that deterministic relationship is the phenomenon being measured, not an added
correlation. It remains a synthetic design choice and is the central caveat.

## 5. Matched structural controls

The equal-total control compares a file-driven dependency package (one object
and one policy access) with an account/history package (one credential and one
history access). Both add two accesses to the same base mediation.

The primary stronger control performs exactly nine accesses in both classes:

```text
Class 0: O P O P O P C H-read H-write
Class 1: O O O C P P P H-read H-write
```

Both contain O×3, P×3, C×1, H×2, eight reads, and one write. Only ordering and
dependency grouping differ. Episode generation is shuffled, labels are balanced,
and no episode ID is a feature. Since the public action has zero entropy, its
mutual information with the hidden label is trivially zero/irrelevant.

## 6. Results

Values are mean ± population standard deviation across three seeds. Chance is
0.500 for the structural probes.

### EQUAL-COUNT STRUCTURAL LEAKAGE

| Variant | Observation | Hidden target | Chance | Accuracy | Permutation |
|---|---|---|---:|---:|---:|
| V2 | F0 total count | equal-count policy mode | .500 | .484 ± .009 | .495 ± .004 |
| V2 | F1 store histogram | equal-count/equal-store policy mode | .500 | .484 ± .009 | .495 ± .004 |
| V2 | F2 ordered stores | equal-count/equal-store/equal-op policy mode | .500 | 1.000 ± .000 | .499 ± .013 |
| V2 | F4 1–3 grams | same strongest control | .500 | 1.000 ± .000 | .499 ± .013 |
| V2 | F5 full allowed ORAM metadata | same strongest control | .500 | 1.000 ± .000 | .507 ± .016 |
| V3 | F2 ordered stores | same strongest control | .500 | .484 ± .009 | .495 ± .004 |
| V3 | F5 full allowed ORAM metadata | same strongest control | .500 | .500 ± .014 | .505 ± .010 |

For the weaker equal-total-only control, F0 accuracy was .496, while F1 store
histograms achieved 1.000; its permutation baseline was .494. Thus equal total
padding removes count signal but not store-composition signal.

The recipient-grouped split trains on recipients 0–11 and tests on 12–15. V2 F3
and F5 accuracy remained 1.000; V3 F5 was .496 ± .016. The result therefore does
not depend on reusing the same recipient identities across train and test.

Path ORAM recipient classification was .076 mean versus .0625 analytical chance
and .067 mean permutation; macro-F1 averaged .057. This small accuracy elevation
is not mirrored by macro-F1 and is not treated as evidence of identity leakage.
Same-recipient linkability ROC-AUC was .495 mean across seeds (individual values
.489, .456, and .539), consistent with chance.

## 7. Simple-padding baselines

| Variant | Address hidden | Count fixed | Store histogram fixed | Sequence fixed | F4 accuracy |
|---|---:|---:|---:|---:|---:|
| V2 | yes | inherent in matched set | inherent in matched set | no | 1.000 ± .000 |
| V2-PAD | yes | yes | inherent in matched set | no | 1.000 ± .000 |
| V2-HIST | yes | yes | yes | no | 1.000 ± .000 |
| V3 | yes | yes | yes | yes | .484 ± .009 |

The matched set already has fixed count and histograms, so V2-PAD and V2-HIST
correctly become no-ops there. This is a feature of the causal control: it shows
that neither baseline can affect the remaining sequence channel. V3 accesses the
same real synthetic records but sorts them into one canonical public schedule.

## 8. Leakage-source analysis

- **Total count:** no signal in the strongest control.
- **Store histogram:** no signal in the strongest control; complete signal in
  the weaker equal-total control.
- **Store order:** first feature level with signal; accuracy rises to 1.000.
- **Operation structure:** not needed for classification, though it is matched.
- **Repetition:** not independently varied; no positive repetition claim is made.
- **Physical ORAM paths:** add no demonstrated leakage beyond store order. V3 F5
  remains at chance, and linkability is at chance.

Publicly exposing store categories is part of the specified Stage-2 threat model.
If stores were themselves multiplexed behind one indistinguishable ORAM endpoint,
this particular ordering signal would disappear; that is an important design
alternative and boundary on the claim.

## 9. Functional correctness

**PASS.** Eight Stage-1/Stage-2 tests pass. V2, V2-PAD, V2-HIST, and V3 return
identical recipient, attachment, sender account, authorization, credential
semantics, and synthetic outcome. V3 length, store sequence, and operation
sequence are invariant; no dummy or logical-block marker is visible.

## 10. Real ORAM overhead

Each primary action performs nine logical ORAM accesses, nine physical path
reads, 72 bucket touches, and 576 fixed-size block transfers (read plus write of
eight buckets at Z=4). At a documented synthetic 4 KiB block size this is a
2.25 MiB transfer proxy per action, not a production network-cost estimate.

| Variant | Mediation µs/action | ORAM µs/access | p50 µs | p95 µs | Mean/max stash |
|---|---:|---:|---:|---:|---:|
| V2 | 294.68 | 29.59 | 26.83 | 46.20 | .007 / 4 |
| V2-PAD | 290.84 | 29.32 | 26.63 | 45.27 | .007 / 4 |
| V2-HIST | 296.11 | 29.11 | 26.73 | 45.43 | .007 / 4 |
| V3 | 351.59 | 34.70 | 31.47 | 53.77 | .009 / 4 |

V2/V0 logical ratio cannot be meaningfully remeasured without mixing Stage-1's
idealized timing, but both use nine logical dependencies in this matched set, so
the logical-count ratio is 1.0. V3/V2 and V3/V0 logical ratios are also 1.0;
V3/V2 physical-transfer ratio is 1.0. V3's 1.19× observed mediation-time ratio
despite identical transfer count is Python microbenchmark variation/key-order
cost, not evidence of an inherent canonicalization cost. Compilation itself is a
small sort but was not isolated reliably; no production latency claim is made.

Sensitivity checks were stable: (64 blocks, Z=4, h=6) had mean/max stash
.008/2; (128,4,7) .017/4; and (128,5,7) .006/3. Every configuration retained
nine logical accesses. This study checks mechanics/overhead, not a large leakage
parameter sweep.

## 11. Scientific interpretation

Stage 2 supports a claim beyond access-count padding in this workload. It also
supports a claim beyond per-store histogram padding: ordered store structure is
sufficient to reveal a private policy mode, and canonical scheduling removes it.
The evidence does **not** establish leakage from ORAM physical paths, repeated
logical references, arbitrary agent frameworks, or real deployments. Nor does it
establish literature novelty.

The perfect V2 result follows from two deterministic synthetic execution modes.
That is appropriate for showing the existence of a structural channel, but the
real-world prevalence and entropy of such modes remain unmeasured. Independent
implementation and preregistered realistic workloads are needed before making
broad empirical claims.

## 12. Implication for ICASSP

There is evidence for a narrowly stronger claim than “ORAM + padding”: under a
host model that exposes private-store categories, matching total accesses and
per-store histograms does not hide a private mediation policy when that policy
changes the store schedule. Schema-driven canonicalization closes that channel
in the synthetic matched workload.

A conservative paper claim is: **logical-address hiding and ordinary count or
histogram padding can leave sequence-level mediation leakage; canonical schedules
remove the demonstrated signal at equal physical access count.** The next study
should independently implement both policy modes in a real mediator, preregister
the causal workload and classifiers, multiplex store visibility as a competing
baseline, and evaluate noisier/non-deterministic scheduling.
