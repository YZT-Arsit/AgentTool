# Per-Action Counterexample

## Smallest natural machine

Consider one public task and one synthetic authorized effect. The mediator has a private session-backed authorization state.

```text
CHECK_AUTHORIZATION
  existing -> PREPARE_EFFECT -> COMMIT_EFFECT
  missing  -> REQUEST_LOCAL_CONSENT_AND_PERSIST
           -> VERIFY_AUTHORIZATION
           -> PREPARE_EFFECT
           -> COMMIT_EFFECT
```

Both branches begin with the same task and end with the same effect. The missing branch is not driven by an artificial hidden label; it follows the ordinary meaning of absent authorization and successful local consent.

## Per-action canonicalization

In B1, every individual mediated round emits exactly three generic `PRIVATE_STATE_ORAM:ORAM_ACCESS` events. No round exposes a logical record, a real/dummy bit, or its private semantic operation. Thus, conditioned on one round's public action class, the private accesses are locally canonical.

But the existing branch has three rounds and the missing branch has five. Concatenating individually canonical actions therefore produces distinguishable trajectories:

\[
View(a_1)\approx View(a'_1)\quad\nRightarrow\quad
View(a_1,a_2,a_3)\approx View(a'_1,a'_2,a'_3,a'_4,a'_5).
\]

The experiment reports B1 structural AUC `1.000 ± 0.000`, while permutation controls average `0.503`. This is the concrete counterexample:

\[
\boxed{\text{Per-Action Mediation Privacy}\not\Rightarrow\text{Bounded Adaptive Mediation Privacy}}
\]

## Public-runtime corroboration

Microsoft Agent Framework independently implements session-backed standing tool approvals, queued approval prompts, and approval responses. On the same measured synthetic task, an existing standing rule completed in one application invocation; an absent rule surfaced an approval request and required a second invocation. Both executed the same local tool once. This is L2 evidence that the state-dependent trajectory shape exists in a public runtime, not evidence that the runtime claims to protect it.

## What the counterexample does not show

It does not establish a new general oblivious-computation principle. It identifies an agent-security composition boundary and demonstrates it in one public approval runtime plus three L1 state-machine scenarios.
