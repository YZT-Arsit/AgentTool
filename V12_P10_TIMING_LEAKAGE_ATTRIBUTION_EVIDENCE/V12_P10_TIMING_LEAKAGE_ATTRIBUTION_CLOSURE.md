# V12 P10 timing leakage-source attribution closure

Role: **POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC**. This work does not replace the
immutable P10 sentinel verdict and is not confirmatory privacy evidence.

## Frozen inputs and execution

- Base P10 result: `558c97bd5ca8bb9123382800cb73eb410cab6342`
- Methodology base: `63792088161deb6b1ccd3c4b4cb28babbf72f3ec`
- Original result: `EARLY_TIMING_DISTINGUISHABILITY`, 6/10 comparisons
- Dataset: 5,040 identities; 5,025 complete; 15 failed
- Selected blocks: 180 TRAIN and 120 EVAL per physical coordinate
- New protected sessions: 0
- Protected runtime diff: NONE

The exact 50 observer-comparison/feature-family results are in
`v12_p10_leakage_attribution_941a89b/observer_feature_family_results.csv` and
the corresponding machine-readable JSON. The slot table contains 2,024 rows:
506 public slots for each of the four Relay T7/T9 coordinates.

## Attribution result

| Original early-fail comparison | Dominant source |
|---|---|
| C1 / OpenAI / Registry | BOTH |
| T7 / OpenAI / Registry | BOTH |
| T7 / OpenAI / Relay | RESPONSE_SIDE |
| T7 / Microsoft / Relay | RESPONSE_SIDE |
| T9 / OpenAI / Relay | RESPONSE_SIDE |
| T9 / Microsoft / Relay | RESPONSE_SIDE |

For both Registry early failures, request-only and response-only remained
distinguishable while query-response latency alone was near chance. For all
four Relay early failures, request-only was near chance, whereas response-only
and slot-paired latency were strongly distinguishable.

## Private mechanism correlation

This correlation was performed only after observer-only attribution completed.
It did not enter any classifier feature.

- Relay T7 classes differ in their second causal transition: median admission
  rounds 4 versus 9 and delivery rounds 5 versus 10. Six (OpenAI) and seven
  (Microsoft) of the 20 largest slot-latency median differences lay within two
  rounds of a median causal transition; none of the top request-timestamp
  differences did.
- Relay T9 classes have systematically different admission/delivery sequences.
  For both frameworks, all 20 largest slot-latency median differences lay
  within two rounds of a median causal transition; the top request-timestamp
  differences did not.
- Registry C1 and T7 class 0 produced 300 real queries across 300 selected
  sessions, while class 1 produced 600. The extra class-1 resolution clustered
  around public ordinal 7. Query-response latency alone was near chance in the
  two original Registry early failures, so the measured signal is principally
  absolute request/response schedule evolution rather than an isolated
  per-query latency effect.

## Response-path audit

Relay response emission is **not independently paced**: the handler waits for
Gateway processing and the full response body, then captures `response_send_ns`
and immediately writes. Gateway work also differs mechanically between NOOP,
REAL, WAIT and RESULT paths.

Registry response emission is **not independently paced**: only query sends are
scheduled; the SimplePIR bridge emits immediately after query/answer/recovery.
The shared algorithmic path alone does not establish a real/dummy processing
time difference, and the diagnostic latency-only results were near chance for
the original Registry early failures.

## Development recommendation

`MIXED_REDESIGN_REQUIRED`.

Changing Relay Delta alone does not directly remove Gateway-coupled response
timing, while the Registry early failures include a separate fixed-PIR
request/response schedule channel. P20 and P25 were not run. Timing privacy
remains inconclusive and timing GO remains NO.
