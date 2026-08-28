# Independent System B: PAuth-derived

## System/source

The source is *Beyond OAuth: Task-Scoped Authorization for AI Agents via Natural
Language Slices* (arXiv:2603.17170v2). The abstraction is conservative and does
not reproduce PAuth's implementation.

## Architecture summary and trust

PAuth makes each server derive an NL slice representing its expected call and
uses signed envelopes to bind server-produced concrete values to symbolic
provenance. Receiving servers verify operations and operands against the slice;
off-slice operations escalate. Envelopes are passed inline, not documented as a
persistent provenance database.

## Architecture-fidelity table

| Component/access | Confidence | Reason | Local abstraction |
|---|---|---|---|
| Private-data lookup | NOT SUPPORTED | Not required by selected authorization check | none |
| Authorization slice | DOCUMENTED; persistence STRONGLY IMPLIED only as an implementation option | Server derives expected symbolic operation | `SLICE_STATE` cache |
| Credential lookup | NOT SUPPORTED | Not part of selected slice/envelope mechanism | none |
| Provenance/history DB | NOT SUPPORTED | Provenance is carried in signed envelopes | inline trusted verification only |
| Authorization decision | DOCUMENTED | Concrete/symbolic consistency check | trusted compute |
| Tool invocation | DOCUMENTED | Authorized server operation | offline mock share |

## Derived workflow and hidden state

The local server loads one cached slice, verifies either a literal operand or an
inline signed-envelope-derived operand, then invokes/denies the mock operation.
Operand origin is the private label, but it causes no persistent storage change.
No second store was invented.

## Audit and results

The pre-classification audit found no change in count, histogram, store order,
or operation order. Every variant has one read from a 1,024-record address space.
Balanced F4 ROC-AUC is exactly .500 for modular, canonical, unified, and unified-
padded variants; accuracy is .474 ± .012 and macro-F1 .322 ± .006 because the
invariant classifier selects one class in slightly imbalanced folds. Full-path
metadata is also at permutation/chance. Grouped-entity accuracy is .512.

Natural 70/30 accuracy matches the .70 majority/permutation baseline and ROC-AUC
is .500. Functional and authorization equivalence pass.

All variants transfer 88 physical blocks (0.344 MiB) per one logical access,
allocate 2,047 tree nodes, and have comparable mean latency of 83.6–85.2 µs.
Canonical and unified variants are structurally irrelevant here.

## Classification and limitations

This is a **NEGATIVE independent validation**. Source-derived PAuth execution
does not naturally provide the heterogeneous persistent-store channel being
tested. The assumed slice cache is weaker-fidelity than GAAP's explicitly
documented databases, but adding more state would make the experiment less
faithful. The negative result limits the project claim to modular architectures
with separately observable persistent security-state services.
