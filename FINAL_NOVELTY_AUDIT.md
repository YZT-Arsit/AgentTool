# Final Novelty Audit

## Focused search result

```text
DIRECT COLLISION: NOT FOUND
```

The search was restricted to the exact concept: private authorization/provenance state changing approval, persistence, retry, or resume steps for the same initial public task and same final public effect in a tool-using LLM agent, observed through the mediation trajectory. Searches covered the mandatory works, current agent-security papers, approval-side-channel terms, authorization workflow privacy, and general oblivious computation.

No inspected work jointly provides all of:

1. private authorization/provenance state as the secret;
2. adaptive multi-step security mediation as the channel;
3. same-task and same-final-effect equivalence;
4. a trajectory observer over approval/persistence/retry/resume structure;
5. a bounded structural privacy definition;
6. an effect-safe transformation with no dummy external effects;
7. validation in public agent runtimes.

The full categorical record is [FINAL_ADAPTIVE_PRIOR_ART_MATRIX.csv](FINAL_ADAPTIVE_PRIOR_ART_MATRIX.csv).

## Closest prior work

### Opal

[Opal](https://arxiv.org/abs/2604.02522) protects personal agent memory by confining data-dependent reasoning to a trusted enclave and exposing fixed oblivious memory accesses to untrusted disk. It is a close systems/formal predecessor for fixed-oblivious agent request traces.

Precise answer: **NO**, Opal's evaluated fixed request trace does not model a private authorization state that triggers additional approval, persistence, retry/resume, and effect-mediation actions. Its secret is personal-memory content/query behavior; the observable boundary is memory retrieval/storage. It does not define effect-equivalent approval trajectories or a no-dummy-external-effect rule.

Limitation: Opal's general design lesson extends immediately—move the private branch into a trusted component and emit a fixed external schedule. Therefore the Stage-10 normalizer is not conceptually novel relative to Opal plus general oblivious computation. The distinction rests on the agent-security mediation abstraction, runtime evidence, effect semantics, and adapter/compiler interface, not on fixed padding.

```text
OPAL COLLISION: PARTIALLY DEFEATED
```

### ObliDB and general oblivious computation

[ObliDB](https://arxiv.org/abs/1710.00458) establishes that individually protected database operations do not ensure end-to-end query obliviousness and provides oblivious query processing across access methods. [ObliVM](https://doi.org/10.1109/SP.2015.29) compiles programs into oblivious representations, while [Taypsi](https://arxiv.org/abs/2311.09393) compiles policy-annotated programs into semantically preserving oblivious computation.

The theoretical answer is broadly **YES**: a bounded approval state machine can be encoded as ordinary oblivious computation, and a sufficiently general compiler can equalize its secret-dependent control flow. Stage 10 does not claim otherwise.

What remains agent-specific is:

- the trusted mediator versus host-visible agent-runtime boundary;
- approval/consent/provenance as the protected state;
- an equivalence class conditioned on the same public task and effect;
- interactive pause, persistence, retry, and resume behavior;
- an effect boundary at which real-world side effects cannot be padded with dummies;
- fail-closed horizon overflow;
- adapters for actual agent approval middleware;
- the empirical finding that per-action protection fails in two public runtimes.

This is enough for a distinct short systems/measurement contribution, but not enough to market the normalizer as a new oblivious compiler.

```text
OBLIDB / GENERAL COLLISION: PARTIALLY DEFEATED
```

### AgentPrint

[AgentPrint](https://arxiv.org/abs/2510.07176) is the closest measurement predecessor. It infers agents and user attributes from encrypted traffic fingerprints produced by agent workflows and tool invocations. It supports the broad point that agent interactivity leaks metadata, but studies network traffic, not private authorization state at a trusted mediator/storage boundary, and does not hold the initial task/effect fixed or provide the proposed transformation.

### Ghost Tool Calls

[Ghost Tool Calls](https://arxiv.org/abs/2606.02483) is the closest agent-runtime privacy abstraction. It treats pre-commit speculative observation as an effect, protects abandoned speculative calls, and reasons explicitly about effect safety. Its abstract states that its issue is speculation/issue time, **not authorization**. It does not protect whether an existing approval caused the runtime to skip an interruption/resume path.

### OCELOT

[OCELOT](https://arxiv.org/abs/2606.12341) treats privacy as cumulative posterior-risk control across an agent trajectory. Its observer sees content released to sinks, and its mechanism chooses declassification variants. It does not hide structural approval/retry counts caused by private mediation state.

### Authorization and provenance systems

[GAAP](https://arxiv.org/abs/2604.19657), [CaMeL](https://arxiv.org/abs/2503.18813), [Fides](https://arxiv.org/abs/2505.23643), [PAuth](https://arxiv.org/abs/2603.17170), and [PACT](https://arxiv.org/abs/2605.11039) protect data flow, capability use, task-scoped authority, or argument provenance. None of the inspected definitions treats variation in trusted approval/persistence/retry/resume structure as a confidentiality channel to the host.

### Content-privacy benchmarks and boundaries

[SlotGuard](https://arxiv.org/abs/2607.17147), [ToolPrivacyBench](https://arxiv.org/abs/2606.28061), and [AgentDAM](https://arxiv.org/abs/2503.09780) study provider-bound transcript bindings, tool-argument over-disclosure, and data minimization. They are complementary content-flow work, not direct mediation-structure collisions.

## Innovation ratings

| Item | Rating | Basis |
|---|---|---|
| I1 — Adaptive agent-mediation leakage identification | **MODERATE** | Exact agent-security channel and same-effect class appear distinct; underlying secret-control-flow leakage is classical |
| I2 — Two-public-runtime empirical validation | **STRONG** | Two independently maintained runtimes, unmodified semantics, identical phenomenon, exact effect equality |
| I3 — Bounded adaptive mediation definition | **MODERATE** | Agent/effect-specific leakage class is useful; formal statement needs the revisions in the security audit |
| I4 — Mediation IR | **MODERATE** | Reused across runtimes and makes effect/visibility boundaries explicit; deliberately small |
| I5 — Normalizer | **INCREMENTAL** | Fixed bounded normalization follows general oblivious compilation/padding principles |
| I6 — Effect-safe/no-dummy-effect adaptation | **MODERATE** | Important agent-specific constraint with fixed commit and fail-closed overflow; not a new transaction primitive |

## Strongest rejection argument

> Generic oblivious computation already handles secret-dependent bounded state machines. The measured runtimes merely instantiate a familiar approval workflow, and the normalizer is fixed padding around it; therefore the mechanism contribution is incremental and the paper risks being an application note.

```text
REJECTION: PARTIALLY DEFEATED
```

The rejection is correct about the mechanism primitive. It is substantially weakened by the two-runtime empirical counterexample to per-action privacy, the agent-specific same-effect leakage class, a common IR rather than two hand-written schedules, and the nontrivial constraint that an agent runtime cannot generate dummy external effects. It is not fully defeated because a reviewer can reasonably value only cryptographic/compiler novelty.

## Strongest acceptance argument

> Private approval state changes the observable security-mediation trajectory in two independent public tool-agent runtimes even when the public task and final real effect are identical. Per-action protection does not compose across interruption, persistence, and resume. A shared mediation IR and bounded, effect-safe normalization make the structural view equal without dummy effects. The work's contribution is the agent-specific problem formulation, public-runtime measurement, formal leakage class, and systems instantiation—not a new ORAM or obliviousness principle.

## Final novelty boundary

Defensible contribution:

1. Identification and measurement of adaptive authorization/provenance mediation as an agent-runtime metadata channel.
2. Same-task/same-effect bounded privacy definition with explicit internal-trajectory protection.
3. Independent validation in two public approval runtimes.
4. A reusable mediation IR and effect-safe instantiation of known oblivious-normalization principles.

Not defensible:

- first secret-dependent control-flow leakage;
- new ORAM, padding, dummy access, or generic oblivious compiler;
- protection of timing, network destination, all trajectories, or unbounded agents;
- novelty over Opal/general oblivious computation at the primitive level.

