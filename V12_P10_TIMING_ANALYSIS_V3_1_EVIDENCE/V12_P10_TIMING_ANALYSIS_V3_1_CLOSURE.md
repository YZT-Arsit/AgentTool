# V12 P10 Timing Analysis Seed-Domain Erratum Closure

The V3.1 erratum maps nonnegative raw protocol seeds into scikit-learn's
accepted integer domain only when constructing estimators. Raw 64-bit seeds
remain unchanged for protocol identity, TRAIN-CV block ordering, and fold-seed
derivation. The protected runtime diff is `NONE`.

The original attempt remains preserved as a pre-fit parameter-validation
failure: one attempted fit call, zero completed classifier fits, zero protected
AUC, zero bootstrap runs, and zero randomization runs.

Before the single decisive analysis, the exact 5,040-identity closed dataset,
all session hashes, 5,025 COMPLETE and 15 FAILED statuses, all ten seed maps,
and the fixed 180 TRAIN / 120 EVAL block inventories were verified. The actual
environment was scikit-learn 1.9.0 and NumPy 2.5.2. All 26 synthetic
pre-analysis tests passed.

## Decisive development-sentinel results

| Task | Framework | Observer | Selected TRAIN model | TRAIN-CV raw AUC | Orientation | TRAIN distinguishability AUC | EVAL AUC | 95% CI | LCB99.5 | Randomization p | Early failure |
|---|---|---|---|---:|---|---:|---:|---|---:|---:|---|
| C1 | OpenAI | Registry | HIST_GRADIENT_BOOSTING | 0.7092901234567901 | NORMAL | 0.7092901234567901 | 0.7457638888888889 | [0.6829861111111111, 0.8049322916666667] | 0.6631930555555555 | 0.00009999000099990002 | YES |
| C1 | Microsoft | Registry | EXTRA_TREES | 0.5464969135802469 | NORMAL | 0.5464969135802469 | 0.5629166666666666 | [0.49027777777777776, 0.6334045138888889] | 0.4661097222222222 | 0.047495250474952504 | NO |
| T4 | OpenAI | Relay | HIST_GRADIENT_BOOSTING | 0.5820987654320988 | NORMAL | 0.5820987654320988 | 0.4644444444444444 | [0.3880520833333333, 0.5413888888888889] | 0.3649982638888889 | 0.8213178682131786 | NO |
| T4 | Microsoft | Relay | HIST_GRADIENT_BOOSTING | 0.44580246913580246 | INVERTED | 0.5541975308641975 | 0.48986111111111114 | [0.4103472222222222, 0.567015625] | 0.38756770833333337 | 0.5982401759824018 | NO |
| T7 | OpenAI | Registry | EXTRA_TREES | 0.6778703703703703 | NORMAL | 0.6778703703703703 | 0.7232638888888889 | [0.6588177083333333, 0.7850729166666667] | 0.6388152777777778 | 0.00009999000099990002 | YES |
| T7 | OpenAI | Relay | HIST_GRADIENT_BOOSTING | 0.9508641975308643 | NORMAL | 0.9508641975308643 | 0.980763888888889 | [0.9681232638888889, 0.9909739583333333] | 0.962221875 | 0.00009999000099990002 | YES |
| T7 | Microsoft | Registry | EXTRA_TREES | 0.6010339506172839 | NORMAL | 0.6010339506172839 | 0.6391666666666667 | [0.5716649305555556, 0.7040972222222223] | 0.549375 | 0.00009999000099990002 | NO |
| T7 | Microsoft | Relay | HIST_GRADIENT_BOOSTING | 0.9679012345679012 | NORMAL | 0.9679012345679012 | 0.9693055555555555 | [0.9468055555555556, 0.9875694444444445] | 0.9374996527777778 | 0.00009999000099990002 | YES |
| T9 | OpenAI | Relay | HIST_GRADIENT_BOOSTING | 0.9778395061728395 | NORMAL | 0.9778395061728395 | 0.9779861111111111 | [0.9579166666666666, 0.9930555555555556] | 0.9504163194444445 | 0.00009999000099990002 | YES |
| T9 | Microsoft | Relay | HIST_GRADIENT_BOOSTING | 0.9860493827160495 | NORMAL | 0.9860493827160495 | 0.9902777777777778 | [0.9809027777777778, 0.9969444444444444] | 0.9765277777777778 | 0.00009999000099990002 | YES |

The predeclared rule is triggered because at least one one-sided LCB99.5 is
strictly greater than 0.55. Therefore:

```text
P10_SENTINEL_TIMING = EARLY_FAIL
P10_SENTINEL = EARLY_TIMING_DISTINGUISHABILITY
READY_FOR_P10_FULL_DEVELOPMENT = NO
TIMING_PRIVACY = INCONCLUSIVE
TIMING_GO = NO
```

No new protected session was executed. P10 full, P20 sentinel, P25 sentinel,
timing confirmation, and the final V12 holdout were not run.
