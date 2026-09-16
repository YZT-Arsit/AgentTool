# V15E final claim matrix

| Claim | Classification | Final evidence and boundary |
|---|---|---|
| Same-Agent unlinkability | **ESTABLISHED** | Complete final APSI+SimplePIR capture; ALL-view TEST AUC 0.487, orientation-invariant 0.513, CI [0.446, 0.526], p=0.7383; direct-ID control 1.0. |
| Cross-session unlinkability | **ESTABLISHED** | Same-slot ALL AUC 0.519, CI [0.490, 0.547], p=0.1009; cross-slot ALL AUC 0.472, orientation-invariant 0.528, CI [0.444, 0.501], p=0.9712; controls 1.0. |
| Ordering privacy | **ESTABLISHED** | Four-class ALL accuracy 0.256, macro-F1 0.256, CI [0.226, 0.286], p=0.3530 against 0.25 chance; control accuracy 1.0. |
| Recurrence privacy | **ESTABLISHED** | `AAA` vs `ABC` ALL AUC 0.463, orientation-invariant 0.537, CI [0.407, 0.521], p=0.8919; control AUC 1.0. |
| Rare-Agent privacy | **ESTABLISHED** | `AAA` vs `AAB` ALL AUC 0.525, CI [0.467, 0.582], p=0.2011; control AUC 1.0. |
| Return-pattern privacy | **NOT_ESTABLISHED** | `ABA` vs `ABC` ALL AUC 0.551, CI [0.495, 0.608], p=0.0389; preserve this significant residual. |
| Structural branch privacy | **ESTABLISHED** | Preserved V15D exact deployed/unprovisioned/idle structural equality and 1/3 structural classification. |
| Structural trajectory privacy | **EMPIRICALLY_SUPPORTED** | Preserved final component-composed four-class result: accuracy 0.2125, CI [0.150, 0.275], with matched unnormalized control 1.0. It is not a fresh integrated 800-session run. |
| Agent-access timing privacy | **NOT_ESTABLISHED** | Preserved V15D deployed/unprovisioned/idle timing accuracy 0.663, CI [0.610, 0.717], p<0.0001. V15E sequence timing results do not override this branch leak. |
| Gateway timing privacy | **NOT_ESTABLISHED** | Preserved strongest final Gateway attack: Microsoft Tool vs Agent-as-Tool AUC 0.645, CI [0.465, 0.818], p=0.0612. |
| Utility | **ESTABLISHED** | Preserved V15D: 240/240 non-idle semantic success and 280/280 profile conformance; zero overflow, silent loss, retrieval failure, or loader failure. |
| 100K scale | **ESTABLISHED** | Preserved real 100K APSI sender and 100K schema-valid artifact SimplePIR store; not 100K independently sourced real-world Agents. |

## Frozen interpretation

`ESTABLISHED` for the access claims is scoped to the labeled-APSI/SimplePIR
cryptographic construction, the complete application-protocol representation,
the declared cloud observer, and the frozen attacker protocol. It is not a
claim of packet-level, microarchitectural, cross-provider, or realized-timing
indistinguishability. An AUC below 0.5 is never interpreted as stronger privacy.

V15E is the final experiment. Statistical failure is reported as evidence, not
used to trigger another redesign.
