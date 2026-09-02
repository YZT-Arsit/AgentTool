# V12 duplex response-lead erratum

The first V4 functional-only requalification was stopped after a common
deterministic gate found one slot whose bounded Gateway response preparation
ended 5.709499 ms after a release based on the original 5 ms lead. No protected
classifier session or AUC was involved.

V4R1 changes only the public response preparation lead from 5 ms to 25 ms. The
response commitment remains `G_i = max(E_i, gateway_application_arrival_i)`;
the public response release moves to `F_i = G_i + 25 ms`, subject to the same
public recurrence. H, Delta, R, Q, byte sizes, forward clock, PIR clock, and
response selection semantics do not change.

The incomplete first functional campaign and all its identities remain
development-only evidence and are never retried.
