# Stage-4 Final Independent Validation Report

## 1. Executive decision

**READY WITH NARROW CLAIM**

One independently proposed architecture, GAAP, explicitly documents the private-
data DB, permission DB, and persistent disclosure log needed to instantiate the
cross-store concern. A source-derived direct-versus-transitive disclosure
workflow produces perfectly distinguishable modular traces at equal count after
per-store Path ORAM, while canonical and unified variants have .500 ROC-AUC.

PAuth is a negative independent case: its source-derived slice/envelope mechanism
does not document heterogeneous persistent mediator state, and the conservative
abstraction produces no trace variation. The paper claim must therefore target
modular privacy runtimes under an explicit host-distinguishable-store deployment
assumption. The broad claim “ORAM is insufficient” is unsupported.

## 2. Why Stage 4 was necessary

Stages 1–2 established an existence result and mechanism; Stage 3 showed a
realistic project-designed state machine plus unified-ORAM alternative. Stage 4
tests external validity: whether independent architecture descriptions yield the
same dependencies without inventing new labels or arbitrary mediator branches.

## 3. Independent architecture selection

- **GAAP** (*An AI Agent Execution Environment to Safeguard User Data*,
  arXiv:2604.19657v1) represents plaintext confinement, IFC, permissions, and
  persistent disclosure accounting.
- **PAuth** (*Beyond OAuth: Task-Scoped Authorization for AI Agents via Natural
  Language Slices*, arXiv:2603.17170v2) represents task-scoped authorization and
  inline signed provenance envelopes.

They were selected for architectural diversity and sufficient primary-source
detail. Full metadata and URLs are in `ARCHITECTURE_SOURCES.md`.

## 4. Source fidelity

GAAP explicitly specifies three databases and their runtime roles. The decisive
added assumption is that these logical DBs become separate, host-distinguishable
ORAM endpoints. PAuth explicitly specifies per-server slices and envelopes but
does not specify a persistent provenance database. Stage 4 assumes only a cached
slice and refuses to add unsupported stores.

| System | Source fidelity | Source-derived persistent components | Added deployment assumption |
|---|---|---|---|
| GAAP-derived | High for semantics; mixed overall | Private-data DB, permission DB, disclosure log | Each DB is a separate ORAM endpoint |
| PAuth-derived | Mixed/conservative | No heterogeneous persistent set documented | One optional ORAM-backed slice cache |

The detailed itemization is in `ARCHITECTURE_FAIRNESS_AUDIT.md`.

## 5. Derived mediation semantics

GAAP direct disclosure reads private data, checks permission, and records the
disclosure. A transitive disclosure begins with data already returned by an
external service, queries the disclosure log to reconstruct earlier private
taint, checks permission, and records the new disclosure. Both execute three
state requests with a read/read/write operation histogram; the first store differs
for a documented reason.

PAuth loads one server slice, verifies either a literal operand or the signed
envelope carried inline with a derived operand, and authorizes the mock operation.
The operand-origin state changes trusted compute but not persistent-state access.

Development traces record `source_semantic_step` and
`source_architecture_component`; classifier-visible traces are independently
serialized and tested to exclude them.

## 6. Host observability assumptions

The modular host sees endpoint/ORAM identity, request count/order, operation, and
physical Path-ORAM path. It cannot see logical record address, content, dummy
status, semantic provenance fields, or private label. Unified variants expose one
endpoint and the same allowed operation/physical metadata. Public action and
coarse episode class remain fixed.

Every ORAM uses identical code, Z=4, 4 KiB blocks, greedy eviction, and stash
policy. Unified capacity is the exact sum of modular capacities. Payload
encryption remains abstracted; this is not a production ORAM implementation.

## 7. Independent System A results

**GAAP-derived evidence category: POSITIVE WITH MATERIAL DEPLOYMENT ASSUMPTION.**

Balanced results, mean ± population standard deviation over three seeds:

| Variant | Accuracy | Macro-F1 | ROC-AUC | Permutation accuracy |
|---|---:|---:|---:|---:|
| MODULAR-ORAM | 1.000 ± .000 | 1.000 ± .000 | 1.000 ± .000 | .509 ± .021 |
| CANONICAL-MODULAR | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |
| UNIFIED-ORAM | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |
| UNIFIED-ORAM-PAD | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |

With invariant features, the simple classifier predicts one class; small fold
imbalance produces .474 accuracy and .322 macro-F1. The exactly .500 ROC-AUC is
the appropriate chance result. F0 total count is at chance; F1 category histogram
is the first feature with 1.000 performance. Full physical metadata changes
nothing. Grouped-entity modular accuracy is 1.000; protected variants are .512.

At the preregistered-in-code natural mixture (30% transitive), modular accuracy,
macro-F1, and AUC are 1.000. Protected accuracy matches the roughly .70 majority/
permutation baseline and ROC-AUC is .500.

## 8. Independent System B results

**PAuth-derived evidence category: NEGATIVE.**

The pre-classification audit reports identical one-read traces for literal and
enveloped operands. Every balanced variant has .500 ROC-AUC, .474 ± .012
accuracy, and .322 ± .006 macro-F1; full physical metadata stays near chance.
Grouped accuracy is .512. Natural-distribution accuracy matches its majority/
permutation baseline and AUC remains .500.

Canonical and unified variants are structurally irrelevant for this one-store,
fixed-work abstraction. This negative result is preserved rather than adding an
unsupported provenance database.

## 9. Cross-system comparison

Cross-architecture classifier transfer was not run. GAAP's label is persistent
taint origin expressed through different documented DBs; PAuth's label is inline
operand provenance with no storage variation. Treating them as the same target
would violate the required semantic-comparability discipline.

| System | Multiple documented states | Audit variation | Modular AUC | Canonical AUC | Unified AUC |
|---|---:|---:|---:|---:|---:|
| Stage-3 reference | yes | sequence | 1.000 | near .500 | near .500 |
| GAAP-derived | yes | category histogram | 1.000 | .500 | .500 |
| PAuth-derived | no | none | .500 | .500 | .500 |

## 10. Modular vs canonical vs unified privacy

For GAAP, canonical modular executes fixed DATA-read, LOG-read, PERMISSION-read,
LOG-write slots, using one indistinguishable dummy. Unified unpadded already
works because both hidden states perform three accesses with the identical
read/read/write sequence. Unified padding is unnecessary for this matched task
but is retained as the mandatory baseline.

The result is stronger than pure count leakage but is category rather than
within-histogram order leakage. Stage 3 supplies the latter mechanism for the
reference mediator; GAAP supplies independent external validity for the broader
cross-store channel.

## 11. Systems cost comparison

GAAP balanced performance:

| Variant | Logical | Physical blocks | Bandwidth | Tree nodes | Mean/p50/p95 µs | Mean/max stash | Dummy fraction |
|---|---:|---:|---:|---:|---:|---:|---:|
| MODULAR-ORAM | 3 | 276 | 1.078 MiB | 8,189 | 242.1/232.7/339.5 | .018/5 | 0 |
| CANONICAL-MODULAR | 4 | 368 | 1.438 MiB | 8,189 | 292.9/279.7/401.6 | .009/6 | .250 |
| UNIFIED-ORAM | 3 | 312 | 1.219 MiB | 8,191 | 342.0/329.4/488.0 | .017/5 | 0 |
| UNIFIED-ORAM-PAD | 4 | 416 | 1.625 MiB | 8,191 | 414.4/397.6/582.0 | .008/4 | .250 |

Canonical modular beats unified padded in blocks/latency, but unpadded unified is
the fair privacy-sufficient baseline here and transfers fewer blocks than
canonical (312 versus 368). Canonical is locally faster in this Python run, but
the conflict between bandwidth and timing precludes a general advantage claim.

PAuth variants all use one access, 88 blocks, .344 MiB, 2,047 tree nodes, and
mean latency 83.6–85.2 µs; privacy transformations add nothing.

## 12. Functional and authorization correctness

**PASS.** All four variants for both systems produce identical synthetic
arguments, selected objects, authorization results, state-update semantics, and
mock outcomes. Authorized examples succeed and explicit synthetic unauthorized
examples are denied. Seventeen cumulative tests pass, including Path-ORAM,
deterministic seed replay, equal parameterization, canonical/unified invariants,
and development/host trace separation.

## 13. External-validity matrix

The auditable matrix is in `EXTERNAL_VALIDITY_MATRIX.csv`. It records one
reference positive, one independent conditional positive, and one independent
negative. This satisfies the requirement for at least one positive external
validation but not a broad two-system generality claim.

## 14. Claim audit

The full audit is in `CLAIM_AUDIT.md`. The supported core is per-store ORAM's
failure to hide cross-store structure under a modular observable-endpoint model,
plus two effective alternatives: schema-canonical modular mediation and unified
ORAM. Unsupported claims include general ORAM insufficiency, universal agent
leakage, production security, universal canonical cost advantage, and priority.

## 15. Remaining caveats

- Neither independent implementation was reproduced; only documented dependency
  structure was abstracted.
- GAAP's positive result depends on an added separately observable ORAM-service
  deployment. The cited paper does not prescribe it.
- PAuth's negative result shows the mechanism is not universal.
- GAAP provides independent category/histogram leakage, not the stronger equal-
  histogram sequence leakage of the project-designed Stage-3 mediator.
- Workloads and values remain synthetic; real prevalence and entropy are unknown.
- Standard-library Naive Bayes substitutes for unavailable scikit-learn. The
  separable category result does not depend on model complexity.
- Simulator microbenchmarks do not establish production system cost.
- No novelty/“first” claim has been validated against the literature.

## 16. Final ICASSP recommendation

Freeze the research question and draft only with the modular deployment boundary
prominent. Position unified ORAM as a serious alternative, not a strawman. Treat
canonical modular mediation as an option that preserves service separation, not
as universally cheaper. Do not add further synthetic scenarios before an
independent implementation or reviewer request.

### Mandatory questions

- **Q1:** Did at least one independent architecture naturally generate private-
  state-dependent modular traces? **YES — GAAP-derived.**
- **Q2:** Without explicit hidden-label trace construction? **YES.** Events come
  from direct-data versus documented transitive-log semantics.
- **Q3:** Observable after Path-ORAM address protection? **YES.**
- **Q4:** Stronger than chance/permutation? **YES: 1.000 versus ≈.50.**
- **Q5:** Did canonical modular reduce it near chance? **YES: .500 AUC.**
- **Q6:** Did unified ORAM eliminate it? **YES for all tested independent tasks.**
- **Q7:** Did canonical retain a fair measurable systems advantage? **INCONCLUSIVE/
  CONFIGURATION-DEPENDENT.** Stage 3 says yes; GAAP bandwidth says no versus
  privacy-sufficient unpadded unified.
- **Q8:** Is the narrow cross-store statement supported? **YES**, with the
  modular separately observable service assumption explicit.
- **Q9:** Is “ORAM is insufficient for privacy-preserving agent mediation”
  supported? **NO.** Unified ORAM is effective.
- **Q10:** Is the empirical core ready to freeze? **YES**, as a narrow conditional
  claim, with source/deployment separation retained.

## 17. Exact recommended paper claim

> In modular privacy-preserving agent runtimes where heterogeneous private and
> security-state services remain distinguishable to the host, protecting each
> service's logical addresses independently can leave cross-store mediation
> structure visible. In source-derived and reference workloads, that structure
> reveals private execution state. Canonical modular schedules and a unified
> oblivious address space both suppress the evaluated channels, with
> configuration-dependent systems tradeoffs.
