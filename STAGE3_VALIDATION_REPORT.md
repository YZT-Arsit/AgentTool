# Stage-3 Validation Report

## 1. Executive conclusion

**ARCHITECTURE-SPECIFIC SUPPORT**

The realistic state machine naturally exposes a private authorization mode from
ordered modular-store accesses under equal total count, equal store histogram,
and equal operation histogram. Canonical modular mediation suppresses it. A
unified ORAM also suppresses that matched store-ordering channel, making it a
viable alternative. In this implementation unified ORAM uses longer paths,
28.3% more physical block transfers, roughly twice the tree nodes, and higher
local latency than canonical modular storage.

The evidence supports a modular-architecture claim, not a general assertion that
ORAM is insufficient. One independent validation is recommended before writing
the core ICASSP story as an empirical systems claim.

## 2. What Stage 3 tested

Stages 1 and 2 established existence and mechanism using controlled schedules.
Stage 3 tested whether an executed mediator state machine generates the channel
for a defensible authorization reason and whether a simpler unified oblivious
address space removes it. Stage-1/2 outputs were preserved; all Stage-3 outputs
are under `results_stage3/` and `figures_stage3/`.

## 3. Reference mediator

The planner-facing action contains opaque contact, content, optional document,
and optional account handles. The trusted mediator:

1. resolves the recipient and reads its private authorization metadata;
2. performs recipient preflight authorization immediately when required;
3. resolves content, optional attachment, and default/explicit sender;
4. performs deferred recipient authorization for batch-safe recipients;
5. checks purpose, optional attachment, and sender policies;
6. resolves the selected credential profile;
7. reads prior disclosure state when private policy enables tracking;
8. writes the audit record;
9. invokes an offline `MockEmailService`, or returns denial;
10. returns a synthetic re-encapsulated message handle.

All concrete values are synthetic, including `person_7@example.invalid` and
`synthetic_account_2`. No network, external API, credential, or third-party
service is used. Trace events arise only when a state-machine storage method is
executed.

## 4. Semantic justification

The detailed access-by-access audit is in [SEMANTIC_JUSTIFICATION.md](SEMANTIC_JUSTIFICATION.md).
The key ordering dependency is stored in the resolved recipient object:
`preflight_required` means recipient authorization must precede materialization
of further private objects; batch-safe recipients permit object gathering before
the same policy checks. The offline classifier label is not passed to the
mediator and does not occur in a trace.

| Scenario | Object accesses | Policy accesses | Credential accesses | History accesses | Reason |
|---|---:|---:|---:|---:|---|
| Minimal text | 3 | 3 | 1 | 1 write | Resolve recipient/content/sender, authorize, authenticate, audit |
| Attachment | 4 | 4 | 1 | 1 write | Adds document and independent disclosure policy |
| Explicit account | 3 | 3 | 1 | 1 write | Selects different sender and credential records |
| Attachment + explicit account | 4 | 4 | 1 | 1 write | Both dependency families |
| History-sensitive | corresponding above | corresponding | 1 | 1 read + 1 write | Enforce prior-disclosure policy and audit |

## 5. Threat model and host observability

The trusted boundary contains mediator memory, plaintext, the position map,
stash, private maps, and mock tool. The honest-but-curious host executes ORAM
storage and sees the following:

| Observable | Modular store | Unified ORAM | Why observable |
|---|---:|---:|---|
| ORAM instance/store ID | yes | no | Distinct modular endpoints; one unified endpoint |
| Total request count | yes | yes | Host processes each request |
| Logical record ID | no | no | Hidden by ORAM |
| Record type | indirectly via endpoint | no | Architecture-dependent routing |
| Physical leaf/path | yes | yes | Server executes the path |
| Read/write operation | yes | yes | Intentionally allowed in this model |
| Coarse local timing | yes | yes | Runtime observation |
| Plaintext/dummy status/private mode | no | no | Remains inside trusted runtime |

The experiment does not study network fingerprinting, external destinations,
tool-provider privacy, TEEs, production credentials, or microarchitectural leaks.

## 6. Modular-store results

The primary matched task predicts private recipient authorization mode. Values
are mean ± population standard deviation over seeds 0, 1, and 2.

| Architecture | Count visible | Store identity visible | Ordering visible | F4 accuracy | Chance | Permutation |
|---|---:|---:|---:|---:|---:|---:|
| MODULAR-V2 | yes | yes | yes | 1.000 ± .000 | .500 | .508 ± .012 |
| MODULAR-V2-PAD | fixed | yes | yes | 1.000 ± .000 | .500 | .508 ± .012 |
| MODULAR-V2-HIST | fixed | fixed histogram | yes | 1.000 ± .000 | .500 | .508 ± .012 |
| MODULAR-V3 | fixed | fixed schedule | fixed | .494 ± .003 | .500 | .489 ± .006 |

F0 total-count and F1 store-histogram accuracy are both .494 ± .003 for every
matched architecture. MODULAR-V2 jumps to 1.000 at F2 ordered stores. This is the
first feature level carrying signal; operation tokens and physical metadata are
not needed. V3 F5 accuracy is .517 ± .015, while its simpler schedule-only
features remain at .494; this is not stable evidence beyond its .491 permutation
control.

The recipient-grouped split trains on recipients 0–11 and tests on 12–15.
MODULAR-V2 remains 1.000; MODULAR-V3 is near chance. Thus the classifier learns
the authorization schedule rather than a reused physical recipient artifact.

## 7. Unified-ORAM results

The unified backend places object, policy, credential, and history records into
one address space. Host traces contain only `UNIFIED_ORAM`, operations, and
physical paths; record type is absent.

| Architecture | Matched F4 accuracy | Matched F5 accuracy | Grouped F4 | Interpretation |
|---|---:|---:|---:|---|
| V2-UNIFIED | .494 ± .003 | .509 ± .011 | .487 ± .011 | Store-order channel removed |
| V2-UNIFIED-PAD | .494 ± .003 | .509 ± .011 | .487 ± .011 | Same on already equal-work set |

Same total count and read/write placement make the unified matched sequences
identical. The allowed physical paths add no stable signal. This is a negative
result for any architecture-independent semantic-trace claim and is central to
the Stage-3 classification.

## 8. Equal-work structural control

Every matched action includes recipient, content, attachment, explicit sender,
four policies, credential, history read, and audit write: eleven accesses with
O×4, P×4, C×1, H×2, ten reads, and one final write.

```text
preflight: O P O O O P P P C H-read H-write
batch:     O O O O P P P P C H-read H-write
```

This order is not manually emitted. The first recipient lookup returns the
private preflight dependency, and subsequent state-machine calls generate the
sequence. Count and histogram padding are no-ops on this already matched set;
canonical modular ordering and unified endpoint hiding each remove the signal.

## 9. Natural-distribution results

The documented natural mixture independently samples attachment presence at
30%, explicit account selection at 20%, and history-sensitive policy at 15%.
The target is history sensitivity. Because it is imbalanced, accuracy chance is
the majority baseline, approximately .85; observed permutation accuracy is
.863 ± .014. A second evaluation keeps attachment/account probabilities and
balances history state at 50%.

| Architecture | Natural accuracy | Natural permutation | Balanced accuracy | Balanced permutation |
|---|---:|---:|---:|---:|
| MODULAR-V2 | 1.000 ± .000 | .838–.863 | 1.000 ± .000 | .496 ± .006 |
| MODULAR-V2-PAD | 1.000 ± .000 | .838–.863 | 1.000 ± .000 | .494 ± .009 |
| MODULAR-V2-HIST | .958 ± .009 | .838–.863 | .845 ± .004 | .496 ± .006 |
| MODULAR-V3 | .863 ± .014 | .863 ± .014 | .504 ± .009 | .508 ± .006 |
| V2-UNIFIED | 1.000 ± .000 | .863 ± .014 | 1.000 ± .000 | .492 ± .009 |
| V2-UNIFIED-PAD | .863 ± .014 | .863 ± .014 | .504 ± .009 | .508 ± .006 |

Unpadded unified ORAM still leaks history state through one extra request; unified
count padding removes all tested natural-workload metadata signal. Modular total
padding leaves store-count signal. Modular histogram padding equalizes counts but
retains placement signal: real history is consulted at its semantic stage, while
padding for non-history cases is inserted with other per-store padding. V3 fixes
the entire schedule and returns to baseline.

## 10. Timing results

Timing is local Python runtime timing, not network timing. No sleeps or artificial
delays were added. On the matched set, timing-only AUC is .506 for MODULAR-V2,
.509 for MODULAR-V3, .514 for unified, and .508 for unified padded: no meaningful
signal. In the natural distribution, the extra history access produces AUC .707
for modular V2 and .663 for unified V2. In the balanced natural set these are
.689 and .630. Padding/canonicalization reduces balanced timing AUC to .538 for
modular count padding, .512 for modular histogram padding, .492 for V3, and .487
for unified padding. These noisy microbenchmarks support only the ordinary
variable-work explanation.

## 11. Functional and authorization correctness

**Functional equivalence: PASS. Authorization equivalence: PASS.**

All six architectures return identical recipient, content, attachment, sender,
credential semantics, authorization result, history-update semantics, and mock
tool outcome. A reserved synthetic recipient with a denying policy is rejected
by every architecture and never invokes a successful send. Twelve cumulative
tests pass, including Path-ORAM mechanics, modular/unified correctness, canonical
invariants, trace-field separation, and dummy-schema indistinguishability.

## 12. Performance / ORAM overhead

Small sizes are objects 1,024; policies 1,024; credentials 128; history 2,048.
Medium multiplies each by four. Z=4 and a synthetic 4 KiB block are used.

| Architecture | Logical accesses | Physical blocks | Mean µs | p95 µs | Bandwidth | Max stash |
|---|---:|---:|---:|---:|---:|---:|
| MODULAR-V2 | 11 | 960 | 730.0 | 941.7 | 3.750 MiB | 5 |
| MODULAR-V2-PAD | 11 | 960 | 861.6 | 1140.6 | 3.750 MiB | 5 |
| MODULAR-V2-HIST | 11 | 960 | 884.8 | 1199.7 | 3.750 MiB | 5 |
| MODULAR-V3 | 11 | 960 | 619.6 | 834.6 | 3.750 MiB | 5 |
| V2-UNIFIED | 11 | 1232 | 1661.4 | 2214.2 | 4.812 MiB | 6 |
| V2-UNIFIED-PAD | 11 | 1232 | 1658.1 | 2203.3 | 4.812 MiB | 6 |

Absolute timings vary with Python process/runtime state, so the short independent
size study is a better architectural comparison:

| Size | Architecture | Tree nodes | Max path | Blocks/action | Mean µs | p95 µs |
|---|---|---:|---:|---:|---:|---:|
| Small | MODULAR-V3 | 8,444 | 12 | 960 | 891.7 | 1444.7 |
| Small | V2-UNIFIED | 16,383 | 14 | 1,232 | 1616.0 | 2103.1 |
| Small | V2-UNIFIED-PAD | 16,383 | 14 | 1,232 | 1637.3 | 2280.7 |
| Medium | MODULAR-V3 | 33,788 | 14 | 1,136 | 1181.9 | 1571.9 |
| Medium | V2-UNIFIED | 65,535 | 16 | 1,408 | 2179.8 | 3022.1 |
| Medium | V2-UNIFIED-PAD | 65,535 | 16 | 1,408 | 2204.1 | 2882.6 |

Unified ORAM is not prohibitively costly here, but canonical modular mediation
uses 22.1% fewer transferred blocks than unified (960 versus 1,232), has shorter
maximum paths, and uses about half as many allocated tree nodes. These are
simulator-local results, not production storage/network measurements.

## 13. Unified-vs-canonical tradeoff

| Property | Canonical modular | Unified ORAM | Unified + padding |
|---|---|---|---|
| Matched privacy | chance | chance | chance |
| Balanced natural privacy | chance | count leaks | chance |
| Small physical blocks/action | 960 | 1,232 | 1,232 |
| Small tree nodes | 8,444 across heterogeneous trees | 16,383 | 16,383 |
| Deployment assumption | Distinct services may remain modular | All private state shares one trust/storage plane | Unified plane plus max-count knowledge |
| Main engineering burden | Schema and dummy-slot maintenance | Namespace, lifecycle, and policy-domain consolidation | Consolidation plus padding |

Canonical modular mediation has a measurable simulator advantage in paths,
bandwidth proxy, tree allocation, and latency. Unified ORAM has the conceptual
advantage of eliminating store-category observations without schema ordering,
but requires consolidating heterogeneous security state and still needs count
padding for variable-work scenarios.

## 14. Scientific caveats

- The mediator is plausible but synthetic; branch prevalence is not measured in
  deployed agent systems.
- Preflight metadata is deterministic per synthetic recipient. Grouped splits
  show structural generalization, but real policies may be noisier.
- The Path ORAM is functional, not cryptographic production storage; client-side
  position-map recursion, authenticated encryption, and system effects are absent.
- A unified endpoint removes the strongest matched channel by construction.
- Naive Bayes is a standard-library fallback because scientific Python packages
  were unavailable; the perfect sequence separation does not require a complex
  model.
- Local timing and memory allocation are noisy and cannot support network or
  production-latency claims.
- No literature novelty claim is made.

## 15. Recommended ICASSP claim

In modular privacy-preserving agent runtimes where heterogeneous security-state
services remain distinguishable to the host, logical-address obliviousness and
count/histogram padding do not necessarily hide the ordered structure generated
by authorization-aware tool mediation. Canonical mediation removes the evaluated
channel while preserving modular storage. A unified ORAM plus count padding is
an alternative with different storage organization and measured simulator cost.

This is an architecture-specific feasibility claim, not evidence that all agents
leak or that ORAM is generally insufficient.

## 16. Recommended final implementation work

Before drafting the empirical core, independently implement the same dependency
semantics in a real mediator framework; preregister workload probabilities and
features; add nondeterministic policy scheduling; compare endpoint multiplexing
without full unified state; use a maintained ORAM library; and repeat performance
measurements in an isolated benchmark process.

## Mandatory claim audit

- **Q1 — Does structural leakage arise from a realistic state machine without
  explicit label-dependent trace construction? YES.**
- **Q2 — Does total-count padding solve it? NO** for modular observable stores.
- **Q3 — Does per-store histogram padding solve it? NO.**
- **Q4 — Does unified ORAM solve it? PARTIALLY.** It solves the matched store-order
  channel; count remains in unpadded natural workloads, while unified padding
  solves all tested metadata probes.
- **Q5 — If unified ORAM solves it, does canonical modular mediation offer a
  measurable systems advantage? YES** in this simulator: fewer transferred
  blocks/tree nodes, shorter paths, and lower latency.
- **Q6 — Does canonical mediation suppress the structural channel? YES.**
- **Q7 — Does the evidence justify “execution-plane mediation-trace leakage”?
  ONLY UNDER MODULAR-STORE ASSUMPTIONS** for the beyond-count structural claim.
- **Q8 — Is the current evidence strong enough for the core ICASSP story?
  NEEDS ONE MORE VALIDATION.**
