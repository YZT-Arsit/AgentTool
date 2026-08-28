# ObliDB vs Adaptive Mediation

Primary source: [ObliDB: Oblivious Query Processing for Secure Databases](https://arxiv.org/abs/1710.00458).

## Is bounded adaptive mediation just an oblivious program?

At the general theoretical level, largely yes. ObliDB explicitly notes that making individual subproblems oblivious does not guarantee an end-to-end workload is oblivious, and it provides oblivious operators and planning over general database workloads. General oblivious computation already requires protection of secret-dependent control flow. Stage 9 does not overturn or replace that principle.

## Domain-specific residue

The Stage-9 contribution candidate is a specialized application of that principle with constraints absent from a conventional database query interface:

- an agent mediation IR for authorization, provenance, consent, verification, and effect control;
- leakage classes that explicitly reveal the final effect type and occurrence;
- a hard prohibition on dummy external effects;
- authorization denials that may not be normalized into success;
- bounded interactive approval/resume trajectories;
- a fixed public commit slot and class-wide fail-closed overflow;
- one public agent runtime measurement of persistent approval state changing the number of application invocations.

These constraints make the application and measurement useful, but the implemented normalizer remains a straightforward bounded control-flow transformation. It does not introduce a new general oblivious operator or optimizer.

## Verdict

```text
OBLIDB COLLISION: PARTIALLY DEFEATED
```

The strongest accurate claim is an agent-security composition counterexample and effect-safe domain formulation, not a new general oblivious-computation theorem.
