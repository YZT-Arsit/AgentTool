# V12 timing statistical protocol V2

Base functional commit: `d3a042aae00033ad2b0cf81b2571b7c428405685`. This revision preserves the historical EVAL-side four-model maximum as prior methodology evidence but supersedes it for all decisive future use.

For each profile/task/framework/observer coordinate, complete matched blocks are split 60% TRAIN and 40% EVAL. Five-fold grouped cross-validation on TRAIN alone ranks the four frozen model families by `max(TRAIN-CV AUC, 1 - TRAIN-CV AUC)`. Score orientation is frozen from TRAIN (`NORMAL` at AUC >= 0.5, otherwise `INVERTED`), with model-name order as the deterministic tie break. The selected model and its preprocessing are then fitted on all TRAIN blocks. Exactly one fixed, TRAIN-oriented score vector is generated on EVAL.

Development split/CV/model seeds are coordinate-specific and derived as the first 64 bits of `SHA256("V12-TIMING-TRAIN-SELECTED-V2-20260831" | profile | task | framework | observer)`. This is a development protocol seed label, not a final V12 holdout seed.

The decisive statistic is the selected model's raw EVAL AUC after applying the TRAIN-frozen orientation. There is no EVAL-side model selection and no `max(EVAL AUC, 1-EVAL AUC)`. EVAL uncertainty uses 10,000 complete matched-block bootstrap resamples without refitting or reselection. Protected development requires the 95th percentile UCB to be at most 0.55. A local control requires the 5th percentile LCB to be at least 0.60. A two-sided 95% interval and within-pair label-randomization p-value are secondary diagnostics.

The frozen full denominator is 900 TRAIN + 600 EVAL = 1,500 blocks per coordinate, or 3,000 sessions. With ten workload comparisons per framework and two frameworks, this is 60,000 sessions per profile. Since every candidate's public schedule floor is 6,000 ms, the serial floor is 100 hours per profile; all three candidates would be 180,000 sessions and 300 hours (12.5 days), excluding startup, analysis, and queueing.

The optional sentinel is independent from the full dataset: 75 TRAIN + 50 EVAL blocks for C1, T4, T7, and T9 in each framework. It can only return `EARLY_STATISTICAL_FAIL` when the one-sided LCB95 is above 0.55; it cannot support a privacy pass or change models, features, tasks, or the frozen full denominator.

No protected trace was read, no protected classifier was trained, and no protected AUC was calculated in this phase.
