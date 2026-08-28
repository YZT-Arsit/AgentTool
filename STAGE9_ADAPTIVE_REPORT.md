# Stage-9 Adaptive Mediation Report

## 1. Executive decision

```text
STAGE-9 DECISION:
ADAPTIVE MEDIATION MAINLINE VALIDATED

L2 PUBLIC RUNTIME:
ACHIEVED
```

The bounded adaptive question survives this audit. Natural private authorization, provenance, and verification state changed multi-round mediation structure while the initial task, successful outcome, and final local effect remained equal. Per-action canonicalization did not compose: B1 remained perfectly distinguishable. The B2 bounded normalizer made every structural round/service/operation/size sequence equal and reduced grouped structural AUC from `1.000` to `0.500`, with identical authorization and effect semantics.

The decision is deliberately narrow. The normalizer is an incremental application of general oblivious-control-flow principles, timing is not protected, and only one public runtime was measured. The agent-specific contribution is rated MODERATE, not STRONG.

## 2. Stage-8 starting point

Stage 8 showed that the strongest per-action variants could produce identical one-action traces, yet an authorization-missing path caused consent, persistence, retry, and another mediated action. That full trajectory remained AUC 1.000. Stage 9 froze the architecture question and tested only whether the trajectory-level distinction could be defined, corroborated in public code, and suppressed without dummy effects.

## 3. Public runtime integration

Stage 9 used the unmodified [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) Python approval middleware at commit `af461de51da16f5cb800ff7febc0f8f96355607a` (MIT). Its documented `ToolApprovalMiddleware` already stores standing rules in session state, queues approval requests, and resumes approved tool calls.

The L2 probe compared a pre-existing standing rule with an absent rule. Both measured runs received `Share DOCUMENT_8 with CONTACT_17` and executed the same synthetic local tool once. The existing rule finished in one application invocation; the absent rule returned an approval request and required a second invocation. No upstream files were patched. The deterministic client and boundary logger are project-added harness code; approval semantics remain upstream.

Details and hashes are in [PUBLIC_RUNTIME_PROVENANCE.md](PUBLIC_RUNTIME_PROVENANCE.md). Exact output is in [public_runtime_probe.json](results_stage9/public_runtime_probe.json).

## 4. Adaptive mediation model

The mediator is modeled as a bounded acyclic state machine \(M=(S,A,\delta)\) with private state \(\sigma\). A run has public maximum horizon \(H\). Bounded Adaptive Mediation Indistinguishability requires executions in the same leakage class to have computationally indistinguishable host views.

This is bounded trajectory privacy. It is not unbounded adaptive-agent privacy. The full definition and assumptions are in [ADAPTIVE_SECURITY_MODEL.md](ADAPTIVE_SECURITY_MODEL.md).

## 5. Allowed leakage

The experiment permits the host to learn the public task/action schema, \(H\), final effect type, final effect occurrence, and public success/failure class. It protects initial authorization/provenance state, whether local consent or extra verification occurred, natural private branch, and natural round count.

The primary view includes rounds, request count, ordered operation/service classes, serialized sizes, and public boundaries. ORAM path tokens are added in the full statistical view. Raw time is evaluated separately.

## 6. Per-action counterexample

B1 makes each individual mediation round exactly three generic ORAM accesses. However, existing authorization produces three rounds while missing authorization plus granted local consent produces five. Individually canonical rounds therefore concatenate into distinguishable trajectories. Provenance and extra-verification scenarios produce the same composition failure with three versus four rounds.

The formal counterexample is in [PER_ACTION_COUNTEREXAMPLE.md](PER_ACTION_COUNTEREXAMPLE.md).

## 7. Mediation IR

The small annotated IR contains resolution, authorization, provenance, consent, persistence, verification, preparation, commit, and sanitized return. Guards declare `public` or `private` visibility. `COMMIT_EFFECT` is the only external-effect operation.

The programs use actual state fields (`permission_exists`, `provenance_exists`, and `requires_extra_verification`), not an experiment label. Ground-truth labels were materialized only after all variant traces for an episode had been captured.

See [MEDIATION_IR.md](MEDIATION_IR.md).

## 8. Adaptive normalization mechanism

`AdaptiveNormalizer.compile(program, H)` enumerates graph paths, calculates the required horizon, and emits fixed public round slots plus a final public commit slot. It does not inspect task names or private guard values. At \(H=5\), each round emits three ORAM-backed private-state access slots. Real semantic operations occupy slots internally; unused slots are dummy accesses with no visible marker. The single real tool effect occurs in the final round.

`SEND_MESSAGE` and `SHARE_DOCUMENT` use the same compiler. Their public endpoint comes from the task schema after compilation. No manually authored task-name schedule exists in the compiler.

## 9. Authorization/effect safety

All positive episodes execute one real effect. No dummy external effect is ever issued. When local consent denies, every variant returns DENY and effect count zero. If \(H\) is too small for any path in the public program class, every state in that class fails closed with `HORIZON_EXCEEDED` before an effect.

## 10. Natural adaptive workloads

The experiment used:

| Scenario | Class 0 | Class 1 | Natural rounds | Final effect |
|---|---|---|---|---|
| Authorization | permission exists | missing, local consent grants and persists | 3 vs 5 | equal |
| Provenance | provenance exists | missing, rebuild and persist | 3 vs 4 | equal |
| Extra verification | cached/current policy | one additional successful verification | 3 vs 4 | equal |

Both `SEND_MESSAGE` and `SHARE_DOCUMENT` were evaluated. Entity and policy profile were sampled independently of the balanced private branch. The run used three seeds, 40 pairs per scenario/task/seed, 1,440 unique episodes, 4,320 variant executions, and 48,960 serialized host events.

A deterministic-planner test covers proposal, private state change, sanitized continuation, follow-up submission, and final effect. No LLM-specific claim is made.

## 11. Structural trace results

Symbolic equality was checked before classification.

| Scenario | Variant | Class signature sets | Grouped-entity structural AUC |
|---|---|---|---:|
| Authorization | B0 NATURAL | disjoint | 1.000 ± 0.000 |
| Authorization | B1 PER-ACTION | disjoint | 1.000 ± 0.000 |
| Authorization | B2 ADAPTIVE | exactly equal | 0.500 ± 0.000 |
| Provenance | B0 NATURAL | disjoint | 1.000 ± 0.000 |
| Provenance | B1 PER-ACTION | disjoint | 1.000 ± 0.000 |
| Provenance | B2 ADAPTIVE | exactly equal | 0.500 ± 0.000 |
| Extra verification | B0 NATURAL | disjoint | 1.000 ± 0.000 |
| Extra verification | B1 PER-ACTION | disjoint | 1.000 ± 0.000 |
| Extra verification | B2 ADAPTIVE | exactly equal | 0.500 ± 0.000 |

“Exactly equal” covers round count, destination/service sequence, operation sequence, and request/response-size sequence. Random physical ORAM paths are intentionally not symbolically equal.

## 12. Statistical results

Because scikit-learn was unavailable, the repository's standard-library multinomial naive-Bayes fallback was used for the nondeterministic full-path and generalization controls. The symbolic result is primary; the classifier is not used to replace it.

Grouped structural ROC-AUC averaged across scenarios:

| Variant | AUC | Analytical chance | Permutation mean |
|---|---:|---:|---:|
| B0 NATURAL | 1.000 | 0.500 | 0.502 |
| B1 PER-ACTION | 1.000 | 0.500 | 0.503 |
| B2 ADAPTIVE | 0.500 | 0.500 | 0.505 |

For B2's full view including randomized physical path tokens, per-scenario grouped AUC ranged from 0.456 to 0.483 with seed standard deviations from 0.016 to 0.099; permutation means ranged from 0.496 to 0.514. This is consistent with noise, not a directional advantage. B2 accuracy was 0.500; macro-F1 was 0.333 because identical features caused deterministic tie-breaking to one class, so ROC-AUC and symbolic equality are the informative metrics.

## 13. Cross-task generalization

Training on `SEND_MESSAGE` and testing on `SHARE_DOCUMENT` yielded structural AUC 1.000 for B0/B1 and 0.500 for B2 in every scenario. Source inspection and tests confirm that the compiler contains neither task name. This demonstrates reuse of the transformation rules, not broad generalization to arbitrary agent programs.

## 14. Horizon sensitivity

| H | Admission | Effects | Structural equality | Mean dummy fraction |
|---:|---|---:|---|---:|
| 3 | all programs overflow and fail closed | 0 | yes | 1.000 |
| 5 | all programs admitted | 1 per episode | yes | 0.733 in the balanced workload |
| 8 | all programs admitted | 1 per episode | yes | higher; class-0 examples 0.875 |

The minimum evaluated public bound supporting every path is 5. A larger bound improves no measured structural privacy because H=5 already achieves equality; it only increases dummy work.

## 15. Functional equivalence

All 4,320 variant comparisons matched B0 on authorization result, permission persistence, provenance state, verification state, effect arguments, effect count, sanitized response, and final outcome. Authorization equivalence and effect equivalence both PASS.

## 16. Overhead

Means over seeds, scenarios, tasks, and branches at H=5:

| Variant | Visible rounds | Real private operations/slots | Dummy slots | ORAM accesses | Wire bytes | Latency µs | Effect latency µs |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 NATURAL | 3.667 | 4.000 | 0.000 | 0.000 | 2,775 | 134.940 | 125.984 |
| B1 PER-ACTION | 3.667 | 4.000 | 7.000 | 11.000 | 5,522 | 343.660 | 270.141 |
| B2 ADAPTIVE | 5.000 | 4.000 | 11.000 | 15.000 | 7,362 | 441.095 | 364.129 |

The reported latency is Python simulator wall time, not a production forecast. Trusted-state inventory averaged about 545 bytes for the small ORAM client abstraction.

## 17. Timing limitation

```text
TIMING REMAINS OUT OF SCOPE
```

No fixed barrier or latency bucket was implemented. The trusted local-consent branch deliberately incurs a real local interaction delay. Mean raw-latency AUC across scenarios remained approximately 0.69 for B2 and was 1.0 for B2 in the authorization scenario. The structural theorem therefore excludes fine-grained timing. This is the most important mechanism limitation.

## 18. Proof sketch

If private accesses are ORAM-oblivious, the compiler emits the same schedule for all private states in one leakage class, real/dummy accesses are host-indistinguishable, and effects occur only at the fixed public commit, then equal leakage implies indistinguishable bounded host views by slot-wise hybrid replacement. The class-wide overflow rule prevents private path length from selecting an observable fallback.

The implemented evidence validates exact structural equality plus randomized physical-path behavior. It does not prove production cryptography or timing security. See [ADAPTIVE_SECURITY_MODEL.md](ADAPTIVE_SECURITY_MODEL.md).

## 19. Opal comparison

[Opal](https://arxiv.org/abs/2604.02522) already keeps query-dependent memory reasoning inside trusted execution and exposes fixed ORAM request shapes. Stage 9 cannot claim fixed observable traces as new. Its narrower difference is private security state changing interactive authorization/effect trajectories under a no-dummy-effect rule. Collision classification: PARTIALLY DEFEATED. See [OPAL_VS_ADAPTIVE_MEDIATION.md](OPAL_VS_ADAPTIVE_MEDIATION.md).

## 20. ObliDB comparison

[ObliDB](https://arxiv.org/abs/1710.00458) explicitly recognizes that individually oblivious components do not make an end-to-end workload oblivious. At a general level, B2 is an oblivious bounded program. The remaining contribution is the agent mediation/effect formulation and L2 measurement, not a new general operator. Collision classification: PARTIALLY DEFEATED. See [OBLIDB_VS_ADAPTIVE_MEDIATION.md](OBLIDB_VS_ADAPTIVE_MEDIATION.md).

## 21. Novelty audit

| Item | Rating |
|---|---|
| N1 per-action leakage | NOT NOVEL |
| N2 adaptive mediation leakage | MODERATE |
| N3 bounded definition | MODERATE |
| N4 mediation IR | WEAK |
| N5 normalizer/compiler | WEAK |
| N6 public-runtime measurement | MODERATE |

The mainline passes because N2, N3, and N6 are MODERATE. See [ADAPTIVE_NOVELTY_AUDIT.md](ADAPTIVE_NOVELTY_AUDIT.md).

## 22. Strongest rejection

The strongest rejection is that general oblivious computation already requires normalization of secret-dependent control flow, and this artifact only builds a tiny bounded machine around a tool call. That criticism is correct about the mechanism and theorem lineage.

## 23. Is rejection defeated?

```text
PARTIALLY
```

The public-runtime standing-approval measurement, per-action composition counterexample, explicit effect leakage classes, no-dummy-effect constraint, authorization safety, and class-wide overflow produce a meaningful agent-security result. They do not establish a new general oblivious-computation technique. The correct framing is a domain-specific problem/definition/measurement contribution with a reference transformation.

## 24. Recommended research direction

Freeze the Stage-9 structural mechanism and research boundary. Do not add more ORAM variants or synthetic privacy scenarios. The next evidence should be a second independent L2 secure-agent runtime with a persistent approval/provenance path, plus expert prior-art review focused on interactive oblivious computation and authorization protocols. If that evidence does not strengthen external validity, position the work as a measurement/formulation contribution rather than a compiler contribution.

```text
ICASSP MAINLINE: CONDITIONAL
NEED ANOTHER SYNTHETIC PRIVACY EXPERIMENT: NO
```
