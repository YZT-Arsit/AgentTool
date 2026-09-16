# Final paper number map after V15E

V15E is the final experiment freeze. Current access-privacy numbers below use
the lossless server-side application-protocol capture. Historical SimplePIR-only
or incomplete-capture numbers are not final-system access results.

## Abstract and conclusion

| Proposed number | Exact source | System status / observer | Sample count and uncertainty | Safe paper wording |
|---|---|---|---|---|
| 100,000 provisioned-Agent artifacts | `FINAL_SCALE_RESULTS.csv` | Current system; real APSI sender and real SimplePIR store | N=100,000; 30 warm real scale queries | "a 100K-record store of schema-valid provisioned-Agent artifacts"; do not say 100K independently collected Agents. |
| 240/240 semantic success | `FINAL_UTILITY_RESULTS.csv` | Current system | 240 non-idle executions; all failures retained | "All 240 measured non-idle executions produced the expected semantic result." |
| 280/280 profile conformance | `FINAL_UTILITY_RESULTS.csv` | Current system | 240 non-idle plus 40 idle sessions | "All 280 measured sessions conformed to the frozen public profile." |
| Same-Agent AUC 0.487 | `V15E_ACCESS_PRIVACY_RESULTS.csv`, `SAME_AGENT_WITHIN_SESSION`, `ALL` | Current system; complete APSI+SimplePIR application-protocol observer | TEST n=800; CI [0.446,0.526]; p=0.7383; invariant 0.513 | "The held-out same-Agent linking attack remained near random guessing under the evaluated observer." |
| Cross-session AUC 0.519 / 0.472 | `V15E_ACCESS_PRIVACY_RESULTS.csv`, same-slot / cross-slot `ALL` | Current system; complete APSI+SimplePIR application-protocol observer | n=1574, CI [0.490,0.547], p=0.1009; n=1558, CI [0.444,0.501], p=0.9712; cross-slot invariant 0.528 | "Both evaluated cross-session linking settings remained near random guessing." Do not describe sub-0.5 AUC as stronger privacy. |
| Ordering/recurrence accuracy 0.256 | `V15E_SEQUENCE_RESULTS.csv`, `FOUR_CLASS_ORDERING_RECURRENCE`, `ALL` | Current system; complete APSI+SimplePIR application-protocol observer | TEST n=800; CI [0.226,0.286]; p=0.3530; chance 0.25 | "Four-way sequence classification was 25.6%, near the 25% random baseline." |
| Return-pattern AUC 0.551 | `V15E_SEQUENCE_RESULTS.csv`, `RETURN_PATTERN_ABA_VS_ABC`, `ALL` | Current system; complete APSI+SimplePIR application-protocol observer | TEST n=400; CI [0.495,0.608]; p=0.0389 | "Return-pattern privacy was not established; the evaluated attack retained a small statistically significant signal." |
| Timing privacy not established | `FINAL_PRIVACY_RESULTS.csv` and `FINAL_TIMING_RESULTS.csv` | Current frozen system; application-level Agent-access timing and Relay timing observers | Branch accuracy 0.663, CI [0.610,0.717], p<0.0001; strongest Gateway AUC 0.645, CI [0.465,0.818], p=0.0612 | "Structural protection does not establish realized timing indistinguishability." |

## Table 1

Use the compact rows in `FINAL_PAPER_TABLE1_V15E.csv`. The precise provenance
for each proposed value is:

| Metric | Exact source | Current vs mechanism-level | Observer / denominator | Statistical evidence and safe wording |
|---|---|---|---|---|
| Provisioned-Agent store: 100,000 | `FINAL_SCALE_RESULTS.csv` | Current system | 100K schema-valid, loadable artifact records | Real APSI and SimplePIR scale evidence; records are not claimed to be independently sourced real-world Agents. |
| Same-Agent linking: AUC 0.487 | `V15E_ACCESS_PRIVACY_RESULTS.csv` | Current system | ALL application-protocol view; TEST n=800 | CI [0.446,0.526], p=0.7383, invariant 0.513. |
| Cross-session same-slot: AUC 0.519 | `V15E_ACCESS_PRIVACY_RESULTS.csv` | Current system | ALL view; TEST n=1574 | CI [0.490,0.547], p=0.1009. |
| Cross-session cross-slot: AUC 0.472 | `V15E_ACCESS_PRIVACY_RESULTS.csv` | Current system | ALL view; TEST n=1558 | CI [0.444,0.501], p=0.9712, invariant 0.528. |
| Ordering/recurrence: accuracy 0.256 | `V15E_SEQUENCE_RESULTS.csv` | Current system | ALL view; TEST n=800; four balanced classes | Macro-F1 0.256; CI [0.226,0.286], p=0.3530; chance 0.25. |
| Return pattern: AUC 0.551 | `V15E_SEQUENCE_RESULTS.csv` | Current system | ALL view; TEST n=400 | CI [0.495,0.608], p=0.0389; label `NOT_ESTABLISHED`. |
| Deployed/unprovisioned/idle structural equality: PASS | `FINAL_SEQUENCE_RESULTS.csv`, `FINAL_STATISTICAL_SUMMARY.json` | Current final pipeline preserved from V15D | Structural fields only; timestamps excluded | Exact equality plus structural classifier accuracy 0.333; do not extend to timing. |
| Trajectory accuracy: 0.2125 | `FINAL_SEQUENCE_RESULTS.csv` | Exact final component composition, not a fresh integrated 800-session campaign | Four-class structural observer; n=800 | CI [0.150,0.275], chance 0.25; matched unnormalized control 1.0. |
| Semantic success: 240/240 | `FINAL_UTILITY_RESULTS.csv` | Current system | Non-idle semantic executions | All failures retained. |
| Profile conformance: 280/280 | `FINAL_UTILITY_RESULTS.csv` | Current system | 240 non-idle and 40 idle sessions | Zero overflow, silent loss, retrieval failure, and loader failure. |
| Retrieval latency: 771.729 / 7466.234 ms | `FINAL_STATISTICAL_SUMMARY.json` | Current system | p50/p95 over 480 successful retrievals | State the successful-retrieval denominator. |
| Task latency: 5002.551 / 14880.534 ms | `FINAL_STATISTICAL_SUMMARY.json` | Current system | p50/p95 over 240 successful non-idle sessions | Semantic completion, not fixed public-session wall time. |
| Base traffic: 9.903 MiB/session | `FINAL_OVERHEAD_RESULTS.csv` | Current public profile | Four Agent-access slots plus frozen 521-cell Gateway profile | Base profile cost; Agent-access and Gateway schedules may overlap in time. |
| Mean measured traffic: 11.318 MiB/execution | `FINAL_OVERHEAD_RESULTS.csv` | Current 280-session workload mix | 320 public profiles, continuation profiles retained | Workload mean; do not conflate with the single-profile cost. |

## Figure 2

Use `FINAL_FIG2_DATA_V15E.csv`. It deliberately includes positive controls,
every final protected Gateway timing setting, the branch-timing residual, and
the return-pattern residual; it is not a success-only selection.

| Figure item | Source / scope | Sample and uncertainty | Safe caption wording |
|---|---|---|---|
| Access linking OAE bars: 0.487, 0.519, 0.472 | `V15E_ACCESS_PRIVACY_RESULTS.csv`; current complete APSI+SimplePIR ALL view | n=800/1574/1558; CIs and p-values are in the figure CSV | "Held-out access-linking AUC under the final joint transcript." |
| Access-linking controls: 1.0 | Same V15E CSV; visible-AgentID projection only | Matching splits and n; CI [1,1], p=0.00009999 | "Unprotected identifier positive control," not a production configuration. |
| Four-class sequence OAE: 0.256; control: 1.0 | `V15E_SEQUENCE_RESULTS.csv`; current ALL view and visible-ID control | n=800; OAE CI [0.226,0.286], p=0.3530 | "Sequence classification approaches the 25% random baseline under OAE." |
| Rare/recurrence/return: 0.525/0.463/0.551 | `V15E_SEQUENCE_RESULTS.csv`; current ALL view | n=400 each; return p=0.0389 | Caption must explicitly identify the residual return-pattern signal. |
| Trajectory: 1.0 to 0.2125 | `FINAL_FIG2_DATA.csv`; matched unnormalized component control and exact final component composition | n=800; OAE CI [0.150,0.275] | Do not call the protected point a fresh integrated session campaign. |
| Branch timing: accuracy 0.663 | `FINAL_PRIVACY_RESULTS.csv`; final-pipeline application timing | n=300; CI [0.610,0.717], p<0.0001; chance 1/3 | Caption must state that branch timing remains distinguishable. |
| Four Gateway OAE AUCs: 0.623, 0.645, 0.443, 0.556 | `FINAL_TIMING_RESULTS.csv`; fresh final protected Relay observer | TEST n=40 per setting; full CIs and p-values in figure CSV | Show all four settings; strongest is Microsoft Tool vs Agent-as-Tool at 0.645. |
| Gateway positive controls: 0.981, 0.969, 0.978, 0.990 | `FINAL_TIMING_RESULTS.csv`; historical matched one-sided component controls | n=80 per setting; CIs in figure CSV | Label as historical component controls, not current unprotected end-to-end executions. |

## Evaluation-section supporting numbers

- Capture: 4,000/4,000 sessions, 12,000/12,000 logical accesses, 16,000/16,000
  APSI captures, and 16,000/16,000 SimplePIR captures. Source:
  `V15E_ACCESS_CAPTURE_SUMMARY.md`. Completeness is 100%; zero observations
  were discarded, retried, replaced, or imputed.
- Exact application objects per slot: APSI OPRF request/response 104/104 B,
  APSI query/result 697,972/1,579,652 B, and SimplePIR query/answer
  36,388/37,196 B. Source: `V15E_ACCESS_CAPTURE_SUMMARY.md`. These are
  application-protocol object sizes, not packet captures.
- Rare insertion (`AAA` vs `AAB`): ALL AUC 0.525, CI [0.467,0.582], p=0.2011,
  TEST n=400. Source: `V15E_SEQUENCE_RESULTS.csv`.
- Recurrence (`AAA` vs `ABC`): train-oriented ALL AUC 0.463,
  orientation-invariant 0.537, CI [0.407,0.521], p=0.8919, TEST n=400.
  Source: `V15E_SEQUENCE_RESULTS.csv`.
- Return (`ABA` vs `ABC`): ALL AUC 0.551, CI [0.495,0.608], p=0.0389,
  TEST n=400. Source: `V15E_SEQUENCE_RESULTS.csv`; privacy is not established.
- Every V15E unprotected visible-ID positive control equals 1.0 with matching
  splits, CI [1,1], and p=0.00009999.
- Dummy heavy Agent, LLM, and Tool executions are 0/0/0. Source:
  `FINAL_OVERHEAD_RESULTS.csv` and `FINAL_STATISTICAL_SUMMARY.json`; dummy PSI,
  PIR, and encrypted frames still execute.
- At N=100,000, the fresh persistent pipeline p50/p95 is 57.173/61.818 ms and
  the measured wire cost is 2,351,400 B per Agent-access opportunity. Source:
  `FINAL_SCALE_RESULTS.csv`; 30 measured queries after preprocessing.

## Numbers to remove from the current manuscript

`NUMBERS_TO_REMOVE_FROM_CURRENT_MANUSCRIPT`:

1. Historical SimplePIR-only linking AUCs `0.490`, `0.476`, and `0.458` wherever
   they are presented as final joint APSI+SimplePIR results. They remain only
   historical mechanism evidence if explicitly labeled.
2. V15D incomplete-capture access results: same-Agent `0.514`, cross-session
   `0.468`/`0.521`, four-class sequence `0.252`, rare insertion `0.558`,
   recurrence `0.478`, and return pattern `0.373`. V15E supersedes them.
3. Historical `1.755 MiB/session` wherever it is presented as final-system
   overhead. The final base profile is 9.903 MiB/session; the measured workload
   mean with continuation profiles is 11.318 MiB/execution.
4. Any wording that claims realized Agent-access or Gateway timing
   indistinguishability. Both remain `NOT_ESTABLISHED`.
5. Any claim that the 100K corpus comprises 100K independently collected
   real-world Agents. It comprises schema-valid provisioned-Agent artifacts.
6. `37,180 B` when described as the full serialized SimplePIR answer. It is the
   matrix payload; the exact serialized object is 37,196 B including its
   16-byte dimension header.
7. Any statement that return-pattern privacy is established. The complete
   V15E ALL-view result is AUC 0.551 with p=0.0389.

## Final claim boundary

The positive access results support empirical resistance under the declared
cloud-visible application-protocol observer, frozen splits, feature views, and
attacker suite. They do not prove packet-level, microarchitectural,
cross-provider, or realized-timing indistinguishability. The final paper must
state both timing limitations and the return-pattern residual.
