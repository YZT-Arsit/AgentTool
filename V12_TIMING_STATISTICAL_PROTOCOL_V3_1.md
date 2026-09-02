# V12 Timing Statistical Protocol V3.1

This narrow pre-outcome erratum supersedes V3 only for scikit-learn estimator
`random_state` representation. The raw unsigned 64-bit protocol seeds remain
unchanged for protocol identity, deterministic TRAIN-CV block ordering, and
the frozen fold-seed derivation.

At estimator construction only, V3.1 applies:

```text
sklearn_random_state = raw_nonnegative_seed mod 2^32
```

The original analysis attempt stopped at the first LogisticRegression
parameter validation. It completed zero classifier fits and produced zero
protected AUC, bootstrap, randomization, or EVAL results. This makes the repair
pre-outcome.

V3.1 does not change the closed 5,040-identity dataset, its 5,025 COMPLETE and
15 FAILED statuses, identities, partitions, priorities, selected 180 TRAIN and
120 EVAL blocks per physical coordinate, observer projections, features,
labels, models, hyperparameters, folds, selection/orientation rules, metrics,
resampling, or sentinel criterion.

The seed-domain manifest records every raw coordinate/fold seed and normalized
estimator seed for all ten observer comparisons. The analysis-input manifest
records every selected block and identity. Both are frozen and hashed before
the single decisive analysis. No new protected session or protected dry run is
authorized.

Protected runtime diff: `NONE`.
