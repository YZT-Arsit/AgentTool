# Final paper number map

All proposed final-system access-privacy values come from V15E's lossless
server-side application-protocol capture. Figure values are generated from
`FINAL_PAPER_PLOT_DATA.csv`; no plotted value is transcribed from prose.

## Abstract and conclusion

| Number | Source | Evidence scope and sample count | Statistical evidence | Safe wording |
|---|---|---|---|---|
| 100,000 artifacts | `FINAL_SCALE_RESULTS.csv` | Current full system; N=100,000, 30 warm queries | Real APSI and SimplePIR | A 100K-record store of schema-valid provisioned-Agent artifacts; not 100K independently collected real-world Agents. |
| 240/240 semantic success | `FINAL_UTILITY_RESULTS.csv` | Current full system; 240 non-idle executions | All failures retained | All 240 measured non-idle executions produced the expected semantic result. |
| 280/280 profile conformance | `FINAL_UTILITY_RESULTS.csv` | Current full system; 240 non-idle plus 40 idle sessions | All failures retained | All 280 measured sessions conformed to the frozen public profiles. |
| Same-Agent AUC 0.487 | `V15E_ACCESS_PRIVACY_RESULTS.csv`, `SAME_AGENT_WITHIN_SESSION|ALL` | Current full system; TEST n=800 | CI [0.446, 0.526], p=0.7383; invariant AUC 0.513 | Same-Agent linking remained near random guessing under the evaluated observer. |
| Cross-session AUC 0.519 / 0.472 | `V15E_ACCESS_PRIVACY_RESULTS.csv`, same-slot/cross-slot `ALL` | Current full system; TEST n=1574/1558 | CI [0.490,0.547], p=0.1009; CI [0.444,0.501], p=0.9712; cross-slot invariant AUC 0.528 | Both evaluated cross-session settings remained near random guessing; never interpret sub-0.5 AUC as stronger privacy. |
| Sequence accuracy 0.256 | `V15E_SEQUENCE_RESULTS.csv`, `FOUR_CLASS_ORDERING_RECURRENCE|ALL` | Current full system; TEST n=800 | CI [0.226,0.286], p=0.3530; chance 0.25 | Four-way access-pattern classification reached 25.6%, near the 25% random baseline. |
| Return-pattern AUC 0.551 | `V15E_SEQUENCE_RESULTS.csv`, `RETURN_PATTERN_ABA_VS_ABC|ALL` | Current full system; TEST n=400 | CI [0.495,0.608], p=0.0389 | Return-pattern privacy is not established; a small statistically significant signal remains. |
| Timing privacy not established | `FINAL_PRIVACY_RESULTS.csv`; `FINAL_TIMING_RESULTS.csv` | Current component and current full-system observers | Branch accuracy 0.663, CI [0.610,0.717], p<0.0001; strongest Gateway AUC 0.645, CI [0.465,0.818], p=0.0612 | Structural protection does not establish realized timing indistinguishability. |

## Evaluation and Table 1

| Metric | Exact source | Current vs historical | Denominator / uncertainty | Safe wording |
|---|---|---|---|---|
| Capture completeness 100% | `V15E_ACCESS_CAPTURE_SUMMARY.md` and frozen V15E inventories | Current full system | 4,000 sessions; 12,000 logical accesses; 16,000 APSI and 16,000 SimplePIR captures; zero discarded | Lossless application-protocol capture, not packet-level capture. |
| APSI sizes 104/104/697972/1579652 B | `V15E_ACCESS_CAPTURE_SUMMARY.md` | Current full system | 16,000 complete observations | Exact serialized OPRF request/response, query, and aggregate result sizes. |
| SimplePIR sizes 36388/37196 B | `V15E_ACCESS_CAPTURE_SUMMARY.md` | Current full system | 16,000 complete observations | Exact serialized query/answer sizes; 37180 B is payload-only and must not be called the full object. |
| Rare insertion AUC 0.525 | `V15E_SEQUENCE_RESULTS.csv`, `RARE_INSERTION_AAA_VS_AAB|ALL` | Current full system | TEST n=400; CI [0.467,0.582], p=0.2011 | No detected rare-insertion signal under the frozen attacker protocol. |
| Recurrence AUC 0.463 | `V15E_SEQUENCE_RESULTS.csv`, `RECURRENCE_AAA_VS_ABC|ALL` | Current full system | TEST n=400; invariant 0.537; CI [0.407,0.521], p=0.8919 | No detected recurrence signal; sub-0.5 orientation is not a stronger-privacy claim. |
| Structural branch equality PASS | `FINAL_SEQUENCE_RESULTS.csv`, `FINAL_STATISTICAL_SUMMARY.json` | Current component | Structural fields only; timing excluded | Deployed, unprovisioned, and idle cases have equal public structural projections. |
| Trajectory accuracy 0.2125 | `FINAL_SEQUENCE_RESULTS.csv`, `FOUR_CLASS_EXECUTION_TRAJECTORY|FINAL_OAE_STRUCTURAL_COMPOSITION` | Current component | TEST n=160; CI [0.150,0.275]; chance 0.25 | Exact final-component composition, not a fresh integrated 800-session campaign. |
| Trajectory control 1.0 | `FINAL_SEQUENCE_RESULTS.csv`, unnormalized endpoint control | Current component positive control | TEST n=160; CI [1,1], p=0.00009999 | The matched attacker recovers the action class when normalization is removed. |
| Utility 240/240 and 280/280 | `FINAL_UTILITY_RESULTS.csv` | Current full system | 240 non-idle and 40 idle sessions | Semantic success and profile conformance are distinct denominators. |
| Failures 0/0/0/0 | `FINAL_STATISTICAL_SUMMARY.json` | Current full system | Overflow, silent loss, retrieval failure, loader failure | Report exact zero counts, not an extrapolated failure probability. |
| Dummy heavy operations 0/0/0 | `FINAL_OVERHEAD_RESULTS.csv` | Current full system | Agent/LLM/Tool counters across 280 sessions | Dummy PSI/PIR and padding frames still execute; no dummy heavy semantic operation executes. |
| Retrieval 771.729/7466.234 ms | `FINAL_STATISTICAL_SUMMARY.json` | Current full system | p50/p95 over 480 successful retrievals | State the successful-retrieval denominator. |
| Task 5002.551/14880.534 ms | `FINAL_STATISTICAL_SUMMARY.json` | Current full system | p50/p95 over 240 successful non-idle sessions | Semantic completion latency, not fixed public-session wall time. |
| Base traffic 9.903 MiB/session | `FINAL_OVERHEAD_RESULTS.csv` | Current full system | 4 APSI+SimplePIR slots plus 521-cell Gateway profile | Agent-access and Gateway schedules may overlap in time; bytes remain additive. |
| Mean traffic 11.318 MiB/execution | `FINAL_OVERHEAD_RESULTS.csv` | Current full system | 280 sessions using 320 public profiles | Workload mean including continuation profiles; do not conflate with base-profile cost. |

## Matched native latency baseline

`FINAL_NATIVE_LATENCY_RESULTS.csv` contains all ten framework/workload
coordinates. Each native coordinate has 10 measured executions, 10 successes,
zero failures, zero retries, no APSI/PIR, no cover schedule, and no Gateway.
OAE values are the matching current-system V15D coordinates.

| Framework / workload | Native p50/p95 ms | OAE p50/p95 ms | Additive p50 ms | p50 ratio |
|---|---:|---:|---:|---:|
| OAI provisioned ordinary | 1.635 / 1.753 | 1177.170 / 1280.167 | 1175.536 | 720.1x |
| OAI unprovisioned ordinary | 1.645 / 1.712 | 7292.604 / 7502.886 | 7290.959 | 4432.0x |
| OAI nested Agent-as-Tool | 5.291 / 5.865 | 1184.363 / 1205.071 | 1179.071 | 223.8x |
| OAI repeated Agent | 4.860 / 12.464 | 1171.670 / 1204.562 | 1166.810 | 241.1x |
| OAI mixed Agent+LLM+Tool | 6.916 / 7.152 | 7290.003 / 7990.002 | 7283.087 | 1054.1x |
| MAF provisioned ordinary | 0.449 / 0.529 | 1168.260 / 1185.927 | 1167.811 | 2602.1x |
| MAF unprovisioned ordinary | 0.417 / 0.425 | 7287.492 / 7316.016 | 7287.075 | 17467.4x |
| MAF nested Agent-as-Tool | 1.276 / 1.303 | 1176.042 / 1206.922 | 1174.766 | 921.8x |
| MAF repeated Agent | 1.184 / 1.202 | 1171.155 / 1190.727 | 1169.971 | 989.2x |
| MAF mixed Agent+LLM+Tool | 1.720 / 1.794 | 7263.527 / 7621.020 | 7261.806 | 4222.1x |

The ratio denominator is an extremely short deterministic local semantic
fixture. Prefer absolute additive latency in the paper and describe ratios as
fixture-specific rather than general deployment slowdowns.

## Figure 2

Every plotted row and its source key appears in `FINAL_FIGURE_NUMBER_AUDIT.md`.

- Panel (a) uses the six current V15E ALL-view AUCs and grouped/bootstrap CIs.
  The return-pattern residual is shown normally and labeled `NOT_ESTABLISHED` in
  the source data.
- Panel (b) uses current V15E four-class access-pattern accuracy and its direct
  identifier control, plus the final structural trajectory component result and
  its matched unnormalized endpoint control. Both classification tasks have
  chance 0.25.
- Panel (c) uses the current branch-timing accuracy plus all four final OAE
  Gateway timing tasks. The four one-sided baselines are historical matched
  component controls and are labeled `HISTORICAL_ABLATION` in the plot data.
- Safe caption boundary: "Structural privacy is the positive guarantee;
  realized Agent-access and Gateway timing privacy are not established."

## Scale figure

`FINAL_SCALE_RESULTS.csv` directly supplies the 1K, 10K, 50K, and 100K points,
30 warm real queries per N. At 100K, PSI p50/p95 is 50.561/58.811 ms, PIR is
56.937/61.575 ms, and the combined pipelined path is 57.173/61.818 ms. The
figure is useful as internal or supplementary evidence; for a four-page ICASSP
submission, the compact Table 1 scale row is the recommended main-text use.

## Numbers to remove or supersede

`NUMBERS_TO_REMOVE_FROM_CURRENT_MANUSCRIPT`:

1. Historical SimplePIR-only linking AUCs 0.490, 0.476, and 0.458 when presented
   as final joint APSI+SimplePIR results.
2. V15D incomplete-capture access results: 0.514, 0.468, 0.521, 0.252, 0.558,
   0.478, and 0.373. V15E supersedes them.
3. Historical 1.755 MiB/session when presented as final-system overhead.
4. Any wording that claims realized Agent-access or Gateway timing
   indistinguishability.
5. Any statement that return-pattern privacy is established.
6. Any statement that all 100K artifacts are independently sourced real-world
   Agents.
7. SimplePIR 37,180 B when described as the complete serialized answer; it is
   the matrix payload, while the application object is 37,196 B.

## Final boundary

The privacy evidence is scoped to the declared cloud-visible application-
protocol observer, frozen grouped splits, feature views, and attacker suite. It
does not prove packet-level, microarchitectural, cross-provider, or realized-
timing indistinguishability. No further experiment or architecture change is
authorized by this freeze.
