# Opal vs. Tool/Security Mediation

Source: [Opal: Private Memory for Personal AI,
arXiv:2604.02522v1](https://arxiv.org/abs/2604.02522).

## What Opal protects

Opal protects personal-memory storage, ingestion, and retrieval for personal AI.
Bulk data resides on untrusted ORAM-backed storage while data-dependent reasoning
and a lightweight knowledge graph remain in a trusted enclave.

## Leakage and fixed shape

The paper identifies retrieval access patterns as the leakage surface and notes
the tension between ORAM's fixed access budget and query-dependent memory
traversal. Opal confines query-dependent reasoning to the enclave so untrusted
disk sees fixed oblivious memory accesses, and it piggybacks ingestion/index
maintenance on those accesses. Queries/ingestion reach trusted computation;
the bulk-store physical accesses remain observable but fixed/oblivious.

## What Stage 8 adds—and does not add

Fixed budgets, dummy work, trusted reasoning, and ORAM are already represented
by Opal and are not contributions here. Stage 8's different computation is a
security/effect mediator: it resolves private provenance, establishes or updates
authorization, invokes a state-changing external tool, persists disclosure
history, and may pause/replan/retry across actions.

The L1 evidence shows:

- per-action provenance service choice leaks under modular deployment, but this
  is only a new workload instance of an old end-to-end principle;
- existing ALLOW versus missing permission produces different bounded
  trajectories even after each action's private-state schedule is fixed;
- the difference persists with trusted-local state because consent and retry are
  actual control/effect semantics, not just disk retrieval.

Thus the **per-action Opal collision is not defeated**. It is **partially
defeated for problem scope** by measured authorization/effect trajectories that
Opal's memory-retrieval workload does not itself model. This does not prove
Opal's techniques cannot be extended; it identifies the extension target.

