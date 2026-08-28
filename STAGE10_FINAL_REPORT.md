# Stage-10 Final Validation Report

## 1. Executive decision

```text
STAGE-10 FINAL DECISION:
A — MAINLINE FROZEN, READY FOR PAPER

Second L2 runtime:
ACHIEVED
```

The Stage-9 claim replicated in a second independently maintained public runtime. In the unmodified OpenAI Agents SDK, a stored approval decision lets a pending tool call continue in one measured runner invocation; the same unresolved call emits an approval interruption and needs a second runner invocation. Both branches start from the identical synthetic public task, execute the identical `send_message` effect exactly once, and return the same sanitized result.

Per-action normalization did not hide the 1-versus-2 continuation structure. The unchanged Stage-9 bounded core emitted equal H=5 structural schedules and reduced the structural score AUC from `1.000` to `0.500`, with no dummy external effects.

A focused literature search found no direct collision with private approval/provenance state leaking specifically through adaptive approval, persistence, retry, and resume structure under same-task/same-effect semantics. General oblivious computation already supplies the normalization principle, so the normalizer remains an incremental component. The coherent short-paper contribution is the agent-specific abstraction, two-runtime evidence, bounded same-effect definition, common IR, and effect-safe instantiation.

## 2. Frozen claim and exclusions

Audited claim:

> Private authorization, approval, or provenance state can change the number and order of trusted mediation steps in an adaptive tool-using agent. This can reveal the private state even if each individual operation is locally protected and the same final public effect occurs.

Audited mitigation:

> Within a public finite horizon, expose a common internal mediation schedule, protect logical private accesses, and release the one real external effect only at a public commit slot.

This report does not claim a new ORAM, padding method, generic oblivious compiler, timing defense, full trajectory privacy, or paper novelty over all oblivious computation.

## 3. Second-runtime selection

The candidate audit covered OpenAI Agents SDK, Microsoft Agent Framework, LangChain/LangGraph, PydanticAI, Google ADK, Semantic Kernel/current Microsoft workflows, AutoGen, and CrewAI. [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) was selected because its [native HITL contract](https://github.com/openai/openai-agents-python/blob/main/docs/human_in_the_loop.md) explicitly checks existing decisions before prompting, surfaces unresolved calls as interruptions, persists decisions in `RunState`, and resumes through `Runner.run`.

The strict candidate table and rejection reasons are in [SECOND_RUNTIME_CANDIDATES.md](SECOND_RUNTIME_CANDIDATES.md).

## 4. Runtime provenance and semantic integrity

```text
Runtime: OpenAI Agents SDK for Python 0.22.0
Commit: a40ae9803e6b7a79faa246293f56adb100d5868b
License: MIT
Upstream working tree: clean
Upstream semantic patches: none
External API/model calls: none
```

The experiment used the SDK's own provider-neutral `ScriptedModel`. Four focused upstream HITL test cases passed. Instrumentation only logs runner boundaries, interruption occurrence, the local synthetic approval action, and the synthetic effect callback. The exact file hashes and source roles are recorded in [SECOND_RUNTIME_PROVENANCE.md](SECOND_RUNTIME_PROVENANCE.md).

## 5. Natural same-effect comparison

Both paths first perform an identical, unmeasured setup: the same public task produces the same pending `send_message` call. The measured continuation differs only in native approval state.

| Property | Approval present | Approval absent |
|---|---:|---:|
| Initial public task | Same | Same |
| Pending tool call and arguments | Same | Same |
| Measured `Runner.run` invocations | 1 | 2 |
| Approval interruptions | 0 | 1 |
| Local approval decisions during measured continuation | 0 | 1 |
| Real tool effects | 1 | 1 |
| Final effect | Identical | Identical |
| Final sanitized result | `completed` | `completed` |
| Final approval state | Approved | Approved |

Symbolic traces:

```text
APPROVAL_PRESENT:
MEDIATION_INVOCATION
-> PUBLIC_EFFECT_COMMIT
-> SANITIZED_RESULT

APPROVAL_ABSENT:
MEDIATION_INVOCATION
-> APPROVAL_INTERRUPTION
-> LOCAL_APPROVAL_DECISION
-> MEDIATION_INVOCATION
-> PUBLIC_EFFECT_COMMIT
-> SANITIZED_RESULT
```

This is native runtime behavior, not a branch on the experiment label.

The SDK's serialized `RunState` remains trusted in this threat model, so raw state bytes/message contents are not exposed as host features. The local native run has no host-visible persistent-storage operation to log. Runner boundary counts and event order are the meaningful serialized-message/continuation structure here; B1/B2 separately expose ORAM-backed internal schedule events.

## 6. B0, B1, and B2

### B0 — NATURAL

The host view contains the actual native boundary sequence above. It is symbolically distinguishable by invocation count, interruption count, sequence length, and effect position.

### B1 — PER-ACTION-OBLIVIOUS

Each runner mediation invocation is represented by the same three generic accesses through the existing Path ORAM abstraction. The natural number of invocations is preserved: one protected round versus two. B1 therefore remains distinguishable even though no logical private address is exposed.

### B2 — BOUNDED-ADAPTIVE-OBLIVIOUS

The Runtime-2 adapter maps SDK approval state/events to the unchanged Stage-9 `AUTHORIZATION` IR. The existing `AdaptiveNormalizer` emits five rounds with three ORAM accesses per round and a fixed final commit. Runtime-specific code does not author the B2 schedule.

The 15 internal accesses are a host-view schedule; the only real external tool callback remains the SDK's one synthetic `send_message` effect. No dummy tool invocation occurs.

## 7. Results

The run used seeds `0, 1, 2`, 20 paired executions per seed and variant, and 360 native SDK branch executions in total. Because the native path is deterministic and the structural signatures are symbolically disjoint/equal, a noisy classifier would add no evidence. We report the interpretable structural score AUC, analytical chance, and shuffled-label control. Entity-group splitting is not meaningful because the experiment intentionally fixes the same public task, call, recipient, and body.

| Variant | Symbolic class relation | Structural-score AUC | Chance | Shuffled-label AUC |
|---|---|---:|---:|---:|
| B0 NATURAL | Distinguishable | `1.000 ± 0.000` | 0.500 | `0.502 ± 0.002` |
| B1 PER-ACTION-OBLIVIOUS | Distinguishable | `1.000 ± 0.000` | 0.500 | `0.502 ± 0.002` |
| B2 BOUNDED-ADAPTIVE-OBLIVIOUS | Exactly equal | `0.500 ± 0.000` | 0.500 | `0.500 ± 0.000` |

The permutation value is the mean of 200 shuffles per seed; the displayed deviation is across the three seed means. Host features/traces and labels are serialized separately in [runtime2_host_runs.csv](results_stage10/runtime2_host_runs.csv) and [runtime2_private_ground_truth.csv](results_stage10/runtime2_private_ground_truth.csv); aggregate rows are in [runtime2_per_seed.csv](results_stage10/runtime2_per_seed.csv).

## 8. Functional and effect equivalence

```text
Authorization result: equal and approved
Approval persistence after completion: equal
Runtime state update: equal final decision
Final effect arguments: exactly equal
Effect count: exactly one in every B0/B1/B2 run
Sanitized final result: equal (`completed`)
Dummy external effects: zero
H=5 overflow: none for the frozen AUTHORIZATION program
```

The B2 compiler-side effect event is a schedule binding for the real SDK effect, not an extra tool invocation. Tests assert that every native and variant record has effect count one.

## 9. Common IR and external validity

Microsoft Agent Framework uses standing session approval rules; OpenAI Agents SDK uses a decision stored for the pending call and can also persist sticky decisions. Their persistence granularity is not identical. Their shared abstraction is nonetheless security-semantic rather than cosmetic:

```text
stored private authority
-> skip approval interruption

missing private authority
-> approval/persistence
-> resume/reinvoke

both
-> same effect once
```

Both adapters use the same Stage-9 IR operations, private/public annotations, H=5 compiler, and commit discipline. This passes the transformation-generality gate for two runtimes while remaining a limited two-framework result. See [CROSS_RUNTIME_COMPARISON.md](CROSS_RUNTIME_COMPARISON.md).

## 10. Timing and overhead

Fine-grained timing privacy remains out of scope. Timing was recorded only as local overhead:

| Native state | Mean measured continuation time |
|---|---:|
| Approval present | 2.129 ms |
| Approval absent | 3.307 ms |

These single-machine Python numbers are not production benchmarks. B2 uses 15 ORAM accesses at H=5. The authorization-only mean dummy fraction is `0.700`; no external dummy effect contributes to that value.

## 11. Focused prior-art collision audit

No direct collision was found. Key boundaries:

- [Opal](https://arxiv.org/abs/2604.02522) fixes oblivious agent-memory request traces but does not model approval/persistence/retry/effect mediation. Its construction is conceptually extensible, limiting mechanism novelty.
- [ObliDB](https://arxiv.org/abs/1710.00458), [ObliVM](https://doi.org/10.1109/SP.2015.29), and [Taypsi](https://arxiv.org/abs/2311.09393) broadly solve secret-dependent computation/control flow. They make the normalizer incremental.
- [AgentPrint](https://arxiv.org/abs/2510.07176) infers private attributes from encrypted agent interaction traffic, but does not isolate approval state under same task/effect.
- [Ghost Tool Calls](https://arxiv.org/abs/2606.02483) is close on agent-runtime trajectory/effect privacy, but explicitly addresses speculation/issue time rather than authorization.
- [OCELOT](https://arxiv.org/abs/2606.12341) budgets cumulative released-content inference, not mediation structure.
- GAAP, CaMeL, Fides, PAuth, and PACT enforce data flow, capabilities, authorization, or provenance without hiding the enforcement trajectory from the host.
- SlotGuard, ToolPrivacyBench, and AgentDAM focus on transcript/tool-content disclosure and data minimization.

The complete matrix is [FINAL_ADAPTIVE_PRIOR_ART_MATRIX.csv](FINAL_ADAPTIVE_PRIOR_ART_MATRIX.csv); the interpretation is in [FINAL_NOVELTY_AUDIT.md](FINAL_NOVELTY_AUDIT.md).

## 12. Security-definition and proof audit

```text
SECURITY DEFINITION:
NEEDS REVISION
```

The implemented proof idea is sound, but `L(tau0)=L(tau1) => View_H(tau0) ~=c View_H(tau1)` is not self-sufficient. The leakage relation must include every public effect attribute, and the theorem must quantify the structural observer, randomness, cryptographic assumptions, error channels, and class-wide horizon overflow behavior.

With those premises explicit, identical public schedules plus ORAM/payload indistinguishability imply computational indistinguishability for the structural observer. Timing remains excluded. The corrected statement is in [FINAL_SECURITY_DEFINITION_AUDIT.md](FINAL_SECURITY_DEFINITION_AUDIT.md).

## 13. Innovation judgment

| Component | Rating |
|---|---|
| Adaptive agent-mediation leakage identification | MODERATE |
| Two-public-runtime empirical validation | STRONG |
| Bounded adaptive mediation definition | MODERATE |
| Mediation IR | MODERATE |
| Normalizer | INCREMENTAL |
| Effect-safe/no-dummy-effect adaptation | MODERATE |

Strongest rejection: generic oblivious computation already handles the bounded state machine, so the work may look like an approval-middleware application. This is **PARTIALLY DEFEATED**, not eliminated. The two-runtime measurement, same-effect class, common IR, and no-dummy-effect constraint support a coherent agent-systems short paper; they do not create a new cryptographic primitive.

## 14. Submission readiness

```text
ICASSP / CCF-B SHORT-PAPER READINESS:
READY WITH MINOR GAPS
```

The research mainline can freeze. Before submission, revise the formal statement, make the public effect projection explicit, and position the normalizer as an instantiation of known oblivious-computation principles. No further synthetic privacy validation or ORAM development is justified. See [FINAL_SUBMISSION_GATE.md](FINAL_SUBMISSION_GATE.md).

## 15. Final contribution list

1. Agent-specific identification and two-runtime measurement of adaptive approval/provenance mediation leakage under same-task/same-effect semantics.
2. A bounded structural privacy definition and mediation IR that protect approval, persistence, retry, and resume occurrence/order.
3. An effect-safe instantiation of known oblivious normalization that equalizes internal mediation trajectories without dummy external effects.

## 16. Reproducibility

```powershell
.venv-stage10\Scripts\python.exe -m stage10_final_validation.runtime2_probe `
  --output results_stage10/runtime2_native_probe.json

.venv-stage10\Scripts\python.exe scripts\run_stage10.py `
  --output-dir results_stage10 `
  --pairs-per-seed 20

python -m pytest -q
```

The experiment is fully local and synthetic. It does not use real accounts, credentials, tool providers, model APIs, or third-party state.
