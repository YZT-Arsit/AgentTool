# Stage-8 Contribution Audit

| Candidate | Novelty | Evidence | Strongest prior art | Defensible? |
|---|---|---|---|---|
| Mediation-trace naming | WEAK | A useful boundary label, no new mechanism | Opal; general access-pattern work | terminology only |
| Real leakage measurement | WEAK | L1 source-faithful RPC traces, not public runtime/deployment | GAAP semantics; Opal synthetic pipeline | not as “real implementation” |
| Per-store non-composition | NOT NOVEL | Per-service ORAM AUC 1.0 from endpoint sequence | ObliDB end-to-end observation | no |
| Formal leakage model | MODERATE | Explicit per-action vs bounded-trajectory view/leakage draft | generic simulation/obliviousness definitions | as agent-specific formalization, not theorem yet |
| Fixed-trace mitigation | NOT NOVEL | Provenance trace sets become identical | Opal and oblivious execution literature | only cost/application data |
| Unified-state design | NOT NOVEL | Provenance AUC at chance/identical shapes | ORAM/oblivious DB designs | baseline only |
| Hybrid/trusted design | WEAK | Trusted-local removes per-action state trace | TEE/client-state placement | systems trade-off only |
| Adaptive-trajectory gap | MODERATE | Missing policy doubles action/trace length; AUC 1.0 after per-action fixed shaping | Opal fixed access budget; generic oblivious state machines | yes, as measured agent workload/problem |
| Enterprise state semantics | MODERATE | Permission freshness/history sharing from Stages 6–8 | authorization and distributed-state literature | as design constraints, not primitive |
| Effect/provenance interaction | MODERATE | Local state-changing effects, authorization acquisition, history commit, retry | transactional agency/audit systems | yes, with narrow scope |

## Candidate scores C1–C7

| Candidate | Rating | Reason |
|---|---|---|
| C1 — New access-pattern principle | NOT NOVEL | Direct collision with Opal/ObliDB/general obliviousness |
| C2 — Agent-tool mediation leakage characterization | MODERATE | Natural L1 traces and cross-entity/policy/task transfer |
| C3 — First realistic measurement of mediation traces | WEAK | L1 is source-faithful, not L2/L3; no “first” claim is supportable |
| C4 — Formal mediation-trace leakage model | MODERATE | Clear leakage function and granularity split, but no proof/composition theorem |
| C5 — Design-space comparison for tool mediation | MODERATE | Four known strategies compared on natural and adaptive workflows |
| C6 — Dynamic/adaptive mediation challenge | MODERATE | Strongest new evidence: per-action defenses leave consent/retry structure |
| C7 — Enterprise shared security-state challenge | MODERATE | Freshness, revocation, history, and effect consistency materially constrain placement |

## Strongest rejection

> This is merely Opal's fixed-trace principle plus ObliDB's end-to-end
> obliviousness observation applied to a GAAP-inspired mediator.

Classification: **PARTIALLY DEFEATED**. It is not defeated for the per-action
finding or mitigation. It is partially defeated by actual L1 traces showing a
bounded adaptive computation—authorization acquisition, policy mutation,
external effect, disclosure provenance, retry—with different privacy and
functionality contracts than memory retrieval or one SQL query. An L2
integration and a formal bounded-trajectory result are still needed.

## Strongest defensible acceptance argument

The work can be accepted as a measurement/design study that identifies and
formalizes the trusted security-mediation boundary in tool agents, validates
natural provenance leakage in a source-faithful runtime, and shows that
per-action protection does not address authorization-dependent adaptive
trajectories. It cannot be accepted as a new ORAM, padding method, fixed-trace
principle, or general non-composition insight.

## Submission-relevance judgment

Does the evidence transform the project into a credible agent-specific
measurement/design contribution? **PARTIALLY.** ICASSP viability is **ADEQUATE
only after reframing toward adaptive mediation**. As a new per-action mechanism,
it is WEAK.

