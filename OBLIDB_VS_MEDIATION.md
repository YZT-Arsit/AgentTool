# ObliDB vs. Tool/Security Mediation

Source: [ObliDB: Oblivious Query Processing for Secure Databases,
arXiv:1710.00458v6](https://arxiv.org/abs/1710.00458). ObliDB explicitly states
that individually protected access methods do not guarantee an oblivious
end-to-end multi-table query.

## Is per-action mediation simply an oblivious multi-table query?

For the Stage-8 provenance probe, **essentially yes**. A trusted program chooses
between private-data and disclosure-history state, consults permissions, and
updates history. Per-service ORAM hides row identity but not the program's
cross-service plan. Unified/fixed execution hides it. That is directly within
the known end-to-end-obliviousness lesson; renaming the program “mediation” does
not establish a new principle.

## Technically meaningful agent-specific remainder

The bounded adaptive workflow spans more than a database query:

- a missing policy causes human authorization acquisition and policy mutation;
- a real (local mock) external effect occurs exactly once;
- audit/provenance state must reflect that effect;
- the planner continues, terminates, or retries based on mediation outcome;
- state is shared across tasks and administrative owners.

These can be represented as a larger oblivious state machine or transaction, so
ObliDB does not become irrelevant. The distinction is the system boundary and
required leakage/functionality contract, not a new cryptographic theorem.

Conclusion: **collision NOT DEFEATED for per-action non-composition; PARTIALLY
DEFEATED for the measurement/design scope of adaptive authorization and effects.**

