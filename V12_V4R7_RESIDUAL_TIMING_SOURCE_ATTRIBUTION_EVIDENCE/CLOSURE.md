# V12 V4R7 residual timing source attribution

Status: **POST_OUTCOME_DEVELOPMENT_DIAGNOSTIC**. This is not confirmatory privacy evidence and does not replace the immutable V4R7 smoke result.

## Frozen inputs and non-actions

- Base smoke: `f66649590f1159a5bce280baaea2cfdc3218435c`
- Dataset: exactly the immutable 640-session smoke inventory.
- Selected blocks: the existing 30 TRAIN and 30 EVAL matched blocks per coordinate.
- New sessions: 0.
- Runtime changes: 0.
- AUC-based privacy claims: 0.
- Paper changes: 0.
- Model, hyperparameter, slot, window, lag, and feature search: none.
- Deadline-miss state entered attacker features: no.

The `ALL` result for every comparison reproduced its immutable smoke selected model and EVAL AUC exactly.

## Predeclared feature-family results

All entries use the same frozen TRAIN-only four-model selection machinery. CIs are two-sided 95% complete-block bootstrap intervals with 10,000 resamples.

| Comparison | Family | Model | TRAIN dAUC | EVAL AUC | CI95 |
|---|---|---:|---:|---:|---:|
| T7/MS/Relay | A | HIST_GRADIENT_BOOSTING | 0.6178 | 0.5333 | [0.3844, 0.6800] |
| T7/MS/Relay | B | RBF_SVM | 0.6078 | 0.5211 | [0.3767, 0.6722] |
| T7/MS/Relay | C | HIST_GRADIENT_BOOSTING | 0.6033 | 0.7067 | [0.5722, 0.8289] |
| T7/MS/Relay | D | HIST_GRADIENT_BOOSTING | 0.6000 | 0.6811 | [0.5378, 0.8089] |
| T7/MS/Relay | AB | HIST_GRADIENT_BOOSTING | 0.6411 | 0.6867 | [0.5478, 0.8133] |
| T7/MS/Relay | BC | EXTRA_TREES | 0.5900 | 0.3978 | [0.2578, 0.5422] |
| T7/MS/Relay | CD | EXTRA_TREES | 0.5156 | 0.5267 | [0.3678, 0.6889] |
| T7/MS/Relay | REQUEST_SIDE | HIST_GRADIENT_BOOSTING | 0.6933 | 0.4756 | [0.3389, 0.6089] |
| T7/MS/Relay | RESPONSE_SIDE | RBF_SVM | 0.5633 | 0.5078 | [0.3911, 0.6272] |
| T7/MS/Relay | ALL | HIST_GRADIENT_BOOSTING | 0.7067 | 0.6711 | [0.5367, 0.7911] |
| T9/OA/Relay | A | RBF_SVM | 0.5811 | 0.6011 | [0.4278, 0.7678] |
| T9/OA/Relay | B | HIST_GRADIENT_BOOSTING | 0.6278 | 0.4544 | [0.2933, 0.6089] |
| T9/OA/Relay | C | HIST_GRADIENT_BOOSTING | 0.6422 | 0.6122 | [0.4600, 0.7589] |
| T9/OA/Relay | D | HIST_GRADIENT_BOOSTING | 0.5856 | 0.6433 | [0.4833, 0.7856] |
| T9/OA/Relay | AB | RBF_SVM | 0.6178 | 0.5989 | [0.4656, 0.7278] |
| T9/OA/Relay | BC | HIST_GRADIENT_BOOSTING | 0.5900 | 0.6611 | [0.5278, 0.7889] |
| T9/OA/Relay | CD | RBF_SVM | 0.5944 | 0.5817 | [0.4511, 0.7100] |
| T9/OA/Relay | REQUEST_SIDE | HIST_GRADIENT_BOOSTING | 0.6600 | 0.3989 | [0.2633, 0.5456] |
| T9/OA/Relay | RESPONSE_SIDE | LOGISTIC_REGRESSION | 0.5844 | 0.4222 | [0.2800, 0.5700] |
| T9/OA/Relay | ALL | EXTRA_TREES | 0.5689 | 0.6844 | [0.5378, 0.8178] |
| T7/OA/Relay | A | HIST_GRADIENT_BOOSTING | 0.7422 | 0.5422 | [0.3889, 0.6933] |
| T7/OA/Relay | B | RBF_SVM | 0.6533 | 0.3633 | [0.2422, 0.4900] |
| T7/OA/Relay | C | EXTRA_TREES | 0.5989 | 0.4878 | [0.3433, 0.6300] |
| T7/OA/Relay | D | HIST_GRADIENT_BOOSTING | 0.6267 | 0.5322 | [0.4011, 0.6656] |
| T7/OA/Relay | AB | HIST_GRADIENT_BOOSTING | 0.6689 | 0.4522 | [0.3122, 0.5900] |
| T7/OA/Relay | BC | RBF_SVM | 0.6378 | 0.5756 | [0.4356, 0.7156] |
| T7/OA/Relay | CD | RBF_SVM | 0.5906 | 0.5178 | [0.4028, 0.6333] |
| T7/OA/Relay | REQUEST_SIDE | HIST_GRADIENT_BOOSTING | 0.6256 | 0.5022 | [0.3589, 0.6478] |
| T7/OA/Relay | RESPONSE_SIDE | LOGISTIC_REGRESSION | 0.5944 | 0.5111 | [0.3533, 0.6656] |
| T7/OA/Relay | ALL | LOGISTIC_REGRESSION | 0.6456 | 0.4856 | [0.3344, 0.6400] |
| T9/MS/Relay | A | RBF_SVM | 0.6006 | 0.5794 | [0.4250, 0.7300] |
| T9/MS/Relay | B | HIST_GRADIENT_BOOSTING | 0.5778 | 0.5022 | [0.3533, 0.6467] |
| T9/MS/Relay | C | LOGISTIC_REGRESSION | 0.5822 | 0.4567 | [0.3089, 0.6067] |
| T9/MS/Relay | D | LOGISTIC_REGRESSION | 0.5944 | 0.4678 | [0.3156, 0.6222] |
| T9/MS/Relay | AB | EXTRA_TREES | 0.6800 | 0.5656 | [0.3911, 0.7300] |
| T9/MS/Relay | BC | LOGISTIC_REGRESSION | 0.6589 | 0.6500 | [0.5011, 0.7867] |
| T9/MS/Relay | CD | LOGISTIC_REGRESSION | 0.5356 | 0.3978 | [0.2500, 0.5522] |
| T9/MS/Relay | REQUEST_SIDE | EXTRA_TREES | 0.5533 | 0.4800 | [0.3322, 0.6278] |
| T9/MS/Relay | RESPONSE_SIDE | EXTRA_TREES | 0.5622 | 0.3872 | [0.2456, 0.5311] |
| T9/MS/Relay | ALL | HIST_GRADIENT_BOOSTING | 0.5944 | 0.4689 | [0.3189, 0.6233] |

The exact unrounded values and feature widths are in `feature_family_results.csv`.

## Slot-level localization

`slot_level_boundary_medians.csv` contains all 1,042 predeclared class-median rows (521 slots for each residual comparison) for boundaries A/B/C/D. No slot-selected classifier was trained.

- T7/Microsoft: A/B's largest median differences were at slots 162-163; C/D's largest differences formed a distinct response-side cluster at slots 156-160. The maximum absolute class-median differences were 0.940 ms (A), 0.937 ms (B), 0.400 ms (C), and 0.405 ms (D).
- T9/OpenAI: C/D differences accumulated at the end of the transcript, dominated by slots 509-521. The maximum absolute differences were 0.250 ms (A), 0.249 ms (B), 0.514 ms (C), and 0.514 ms (D).

These descriptive localizations were not used to choose classifier inputs.

## Private deadline-miss diagnostic

The immutable raw records contain 13 allowed misses. Their slips ranged to 139,089,337 ns (median 69,194,294 ns; p95 138,354,688 ns).

| Coordinate | class 0 | class 1 | Miss slots |
|---|---:|---:|---|
| C1/OpenAI | 1 | 0 | 1 |
| T7/OpenAI | 0 | 2 | 1, 1 |
| T7/Microsoft | 2 | 1 | 1, 25; 1 |
| T9/OpenAI | 0 | 2 | 1, 1 |
| T9/Microsoft | 5 | 0 | 1, 25, 97, 19, 28 |

The misses do not mechanically align with the residual signals. T7/OpenAI had class-1 misses but its ALL AUC was 0.4856; T9/Microsoft had the most misses, all in class 0, but its ALL AUC was 0.4689. The residual slot-median peaks also did not coincide with the miss-slot inventory. This rules out a common late-frame/miss explanation; it does not prove that individual outliers have zero influence.

## Classification and recommendation

- `T7/Microsoft/Relay = RESPONSE_SIDE`. A and B were near chance, while C and D retained the strongest boundary-local signal. CD was near chance, so ordinary Relay response-forward latency is not the identified source.
- `T9/OpenAI/Relay = CROSS_BOUNDARY_CORRELATION`. BC and ALL were strongest, while no single boundary family isolated the full signal.

`NEXT_STEP_RECOMMENDATION = ONE_TARGETED_RUNTIME_REPAIR_THEN_REPEAT_640_SMOKE`

The target is the Gateway-to-Relay response-release timeline and its cross-boundary anchoring. Any repair must be separately frozen and use fresh identities; this diagnostic does not authorize a runtime change.

`TIMING_PRIVACY = INCONCLUSIVE`

`TIMING_GO = NO`

## Analysis execution note

The one frozen analysis completed all model fits and bootstraps and wrote `attribution_analysis.json`. Its subsequent convenience-CSV write failed because the first CSV field inventory omitted the `reproduces_original_smoke_result` key present on ALL rows. No statistical analysis was rerun. The complete feature-family CSV was materialized from the already-written JSON; the already-computed slot-median table was deterministically re-materialized without classifier fitting or AUC/bootstrap calculation.
