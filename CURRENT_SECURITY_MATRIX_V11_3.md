# Current V11.3 security matrix

| Item | Status | Evidence / boundary |
|---|---|---|
| V11.2 online ingress, single session, live results, dynamic SimplePIR | PASS (preserved) | `V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json` |
| V11.2 negative 17/20 | PASS (preserved) | Not relabeled; 3 admission closures remain |
| Predeclared candidate selection rule | PASS | 1,000 sessions; no candidate selected |
| Online admission profile | FAIL | A=300 fifty-action stratum 0/20 |
| Online reliability final | NOT RUN | Requires selected profile |
| Action-count public invariant | NOT RUN | Requires selected profile |
| Causal-depth public invariant | NOT RUN | Requires selected profile |
| Finite-horizon deliberate negative | NOT RUN | Requires selected profile |
| Online semantic regression | NOT RUN | Requires selected profile |
| Online structural/size regression | NOT RUN | Requires selected profile |
| Dummy heavy operations in qualification | PASS | Aggregate 0 |
| Profile overflow in qualification | PASS | Aggregate 0 |
| Silent committed-result loss in qualification | PASS | Aggregate 0 |
| Timing privacy | OPEN / NOT TESTED | No timing classifier |
| Packet-level timing | OPEN | Out of this phase |
| Hardware TEE | NOT_TESTED | Not a software-profile blocker |
| Frozen action mediation corpus | 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED | Unchanged |
| Source-body executable subset | 0 | Unchanged |
| V10/V10.1 selected outcomes observed | NO | No holdout path called |
