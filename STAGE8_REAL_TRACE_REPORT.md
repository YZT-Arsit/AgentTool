# Stage-8 Realistic Agent-Mediation Trace Validation and Contribution Audit

## 1. Executive result

**STAGE-8 DECISION: REFRAME TOWARD ADAPTIVE MEDIATION.**

Natural private-state-dependent trace variation exists in an L1 source-faithful
mediator, but the per-action result is an application of known end-to-end
obliviousness principles. The stronger evidence is that authorization
acquisition, policy persistence, effects, audit/provenance, and retry create a
private-state-dependent bounded trajectory even after each action's private
state schedule is fixed. Contribution strength is **MODERATE** and ICASSP
viability is **ADEQUATE only under this reframe**. The current mechanism must not
be claimed novel.

## 2. Mediator source/provenance

The implementation is explicitly **SOURCE-FAITHFUL REFERENCE IMPLEMENTATION —
L1**, not GAAP code. The primary source is Stanley et al., [*An AI Agent
Execution Environment to Safeguard User Data*, arXiv:2604.19657v1](https://arxiv.org/abs/2604.19657).
It documents private-data and permission databases, a persistent disclosure log,
IFC/taint tracking, intercepted MCP calls, dynamic user permission acquisition,
and multi-shot execution. No official code repository was located; the paper
says release is planned. Provenance per operation is in
`TRACE_PROVENANCE_AUDIT.md`.

## 3. Exact deployment model

The trusted mediator uses a deterministic planner and synthetic enterprise
state. State/effect/user roles run as nine real localhost service processes.
Every observed operation is a serialized TCP request/response; 21,535 raw events
were captured. Original modular service separation is a project deployment
assumption, not a claim about GAAP's actual unpublished implementation.
The processes provide transport-faithful protected-payload acknowledgments;
plaintext semantics execute from the trusted reference state image. This is not
a storage-engine or cryptographic reproduction.

## 4. Threat model

The cloud planner and modular infrastructure observer are untrusted for private
state; mediator control flow and plaintext are trusted. The observer sees
service/port identity, operation class, order, request/response size, timing,
stable direct address tokens or ORAM physical paths, public action class/count,
and episode boundaries. It cannot inspect trusted memory or protected payloads.
All tasks, data, parties, policies, and effects are local and synthetic.

## 5. Host observation model

Service identity follows from destination port; byte sizes from framed TCP;
timing/order from host scheduling; direct stable address from storage location;
ORAM path from physical service work; action type/count from the allowed leakage
class. Host files exclude entity/logical IDs, taint origin, permission/consent
values, plaintext, labels, and dummy markers. Ground truth is stored separately.

## 6. Tasks

The deterministic planner executes SEND_MESSAGE, SHARE_DOCUMENT, CREATE_EVENT,
and FORWARD_INFORMATION. Each invokes a distinct local state-changing mock tool
only after authorization and persists disclosure provenance. No LLM was used;
no LLM-specific empirical claim is made.

## 7. Private semantic variables

`requires_history` means a value has persistent transitive provenance rather
than a direct private-DB source. `permission_missing` means the item/party pair
requires user consent and policy persistence. Entity, project, policy profile,
permission, consent, prior disclosure, and taint origin are sampled as
enterprise state before the task. Labels are derived only after trace capture.

## 8. Natural execution traces

For an existing ALLOW and one public action, source-derived runtime behavior is:

```text
direct:      PRIVATE_DATA_DB -> PERMISSION_DB -> TOOL -> DISCLOSURE_LOG
transitive:  DISCLOSURE_LOG  -> PERMISSION_DB -> TOOL -> DISCLOSURE_LOG
```

Both have four calls; only the state-service sequence differs. The branch tests
the pre-existing taint descriptor because GAAP semantics require either direct
lookup or persistent-taint recovery. No evaluation label reaches runtime.

## 9. Symbolic trace analysis

Original and Per-service ORAM provenance classes have disjoint endpoint
sequences (Jaccard 0), so the distinction is deterministic and needs no ML.
Unified, fixed-canonical, and trusted-local sequence sets are identical
(Jaccard 1). Request counts are equal in the per-action probe. Detailed length,
endpoint, byte, and timing distributions are in
`results_stage8/symbolic_distinguishability.csv`.

## 10. Statistical/inference analysis

A standard-library Multinomial Naive Bayes fallback was used because numpy,
scikit-learn, pandas, and matplotlib are unavailable. It operates only on
host-visible endpoint/operation n-grams, counts, bytes, timing bins, paths, and
stable tokens. Symbolic results remain primary.

| Variant | Grouped entity | Cross policy | SEND→SHARE | Permutation (grouped) |
|---|---:|---:|---:|---:|
| Original mediator | 1.000 ± .000 | 1.000 ± .000 | 1.000 ± .000 | .479 |
| Per-service ORAM | 1.000 ± .000 | 1.000 ± .000 | 1.000 ± .000 | .479 |
| Unified oblivious | .449 ± .095 | .444 ± .008 | .500 ± .000 | .466 |
| Fixed canonical | .449 ± .095 | .444 ± .008 | .500 ± .000 | .466 |
| Trusted local | .449 ± .095 | .444 ± .008 | .500 ± .000 | .465 |

Analytical chance is .5. Protected fluctuations are finite-sample/model noise,
not leakage: their symbolic feature distributions are identical and cross-task
is exactly chance. Thirty-two label permutations per seed stabilize controls.

## 11. Dynamic planning traces

An existing ALLOW completes in one action. A missing policy invokes consent,
persists the decision, and retries; when consent is ALLOW, both cases ultimately
produce one identical effect. Trace lengths are 4→8 for Original,
Per-service, and Unified; 6→12 for Fixed; and 1→2 for Trusted-local. Every
variant has grouped-entity and cross-policy AUC 1.000, with permutation near
.5. Thus per-action protection is not bounded-trajectory protection.

## 12. Effect-producing workflow

All four tasks execute a local mock effect only after authorization, append
disclosure provenance, and expose the public tool destination/effect occurrence.
The adaptive comparison holds final effect count fixed at one, so its difference
comes from missing-policy acquisition and retry rather than “effect versus no
effect.” Stage 7's idempotency/atomicity protocol is not re-claimed here.

## 13. Baselines

- **ORIGINAL-MEDIATOR:** source-faithful direct modular services; not called
  insecure under its own threat model.
- **PER-SERVICE-ORAM:** naturally distinct services, generic ORAM method/path;
  hides address but retains endpoint sequence.
- **UNIFIED-OBLIVIOUS:** one generic oblivious endpoint for external state;
  suppresses per-action provenance signal.
- **TRUSTED-LOCAL:** relevant state local, with Stage-6 freshness semantics as a
  deployment requirement; suppresses per-action state trace.
- **FIXED-CANONICAL:** known oblivious-execution technique executing maximum
  state slots; suppresses per-action provenance but not consent/retry trajectory.

## 14. Mitigation results

Unified/fixed/trusted eliminate the measured per-action provenance distinction.
Fixed costs 7.66 mean events/episode versus 4.60 for Original/Per-service/Unified;
Trusted-local exposes 0.96. Mean wire bytes are 2,362/2,312/2,310/3,837/495 in
Original/Per-service/Unified/Fixed/Trusted order. These are local transport
measurements, not production ORAM costs. None hides adaptive consent/retry.

## 15. Opal comparison

[Opal](https://arxiv.org/abs/2604.02522) protects personal-memory
ingestion/retrieval by moving data-dependent reasoning into a trusted enclave
and presenting fixed oblivious accesses to untrusted disk. Therefore trusted
reasoning plus fixed ORAM trace is prior art. Stage 8 differs in measured
computation—authorization acquisition, external effects, persistent disclosure
provenance, and retries—but does not show that Opal's approach cannot extend to
it. Collision: **PARTIALLY DEFEATED for scope, not mechanism**.

## 16. ObliDB comparison

[ObliDB](https://arxiv.org/abs/1710.00458) already states that independently
protected access methods do not make a multi-access-method workload oblivious.
The per-action mediation result is essentially an oblivious multi-table/program
problem, so that collision is **NOT DEFEATED**. The adaptive user/effect workflow
partially distinguishes the application boundary, not the general principle.

## 17. Agent-specific distinctions

The technically meaningful remainder is the interaction among persistent
authorization provenance, user policy acquisition, externally visible
state-changing tools, audit consistency, and planner continuation across tasks.
These impose a leakage/functionality contract beyond memory retrieval. They can
still be modeled by generic oblivious computation, so the contribution is a
characterization/formalization/design study rather than a new primitive.

## 18. Formal leakage-function draft

Let `P` be mediator plus deterministic planner, `sigma` private enterprise
state, `View_H(P,sigma)` the ordered host events, and `L(P,sigma)` allowed
leakage. Public leakage is task/public action class, external tool destination,
authorized effect occurrence, configured store geometry, action/episode count,
and recovery occurrence. Protected state is provenance origin/history
requirement, logical object/entity, permission occupancy/value, consent value,
and policy/history contents.

Candidate condition:

```text
L(P, sigma_0) = L(P, sigma_1)
    =>
View_H(P, sigma_0) ≈ View_H(P, sigma_1)
```

Fixed/Unified/Trusted satisfy the evaluated **per-action** provenance instance
when action and effect are fixed. They do **not** satisfy the evaluated bounded
adaptive trajectory instance if action count is removed from allowed leakage.
No full adaptive-trajectory guarantee is claimed.

## 19. Contribution audit

C1 new principle is NOT NOVEL. C2 characterization, C4 formal abstraction, C5
design comparison, C6 adaptive challenge, and C7 enterprise state semantics are
MODERATE but narrow. C3 “first realistic measurement” is WEAK because evidence
is L1, not L2/L3. Submission-relevance answer: **PARTIALLY**. See
`CONTRIBUTION_AUDIT.md` and `NOVELTY_MATRIX.csv`.

## 20. Strongest rejection argument

> This is merely Opal's fixed-trace principle plus ObliDB's end-to-end
> obliviousness observation applied to a GAAP-inspired mediator.

This is correct for the per-action leakage and mitigation. The L1 cross-task
measurement alone does not defeat it.

## 21. Is rejection defeated?

**PARTIALLY DEFEATED.** Actual source-faithful RPC traces, independent state
generation, grouped transfer, real local effects, and the residual
authorization-dependent trajectory make the work more than the earlier
label-to-endpoint construction. But only adaptive security mediation, not the
obliviousness mechanism, remains plausibly agent-specific. L2 evidence is still
missing.

## 22. ICASSP viability

**ADEQUATE if reframed toward adaptive mediation; WEAK as the current per-action
mechanism story.** A coherent short contribution could combine (A) L1/L2
mediation-trace measurement, (B) an agent-specific bounded-trajectory leakage
abstraction, and (C) cost/semantic comparison of known mitigations. It must not
claim new ORAM, fixed tracing, dummy padding, or generic non-composition.

## 23. Remaining blockers

The primary blocker is external validity: no official GAAP runtime was available,
so evidence stops at L1. Next work should integrate trace capture into an L2
secure-agent implementation, test genuine planner/tool results without exposing
private labels, formalize bounded adaptive leakage and allowed effect leakage,
and evaluate whether trajectory padding can preserve user interaction and effect
semantics at acceptable cost. No additional label-driven synthetic privacy
experiment is recommended.
