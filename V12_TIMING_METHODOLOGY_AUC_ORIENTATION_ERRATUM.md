# V12 timing methodology AUC-orientation erratum

This append-only erratum applies before any real timing data is evaluated. It
does not rewrite the methodology closure at commit
`20cf66a1bf1d3c5b588d67325284dcb7ec92d6ee`.

Raw ROC AUC depends on protected-label polarity. The decisive metric is now:

`DISTINGUISHABILITY_AUC(a) = max(a, 1-a)`

and the frozen family statistic is the maximum distinguishability AUC across
the four fixed models. The same orientation transformation occurs inside each
complete-EVAL-block bootstrap replicate before the model-family maximum is
taken. Its range is `[0.5, 1.0]`.

Deterministic synthetic tests freeze the mappings `0.40 -> 0.60`,
`0.50 -> 0.50`, and `0.80 -> 0.80`. No classifier was trained on real traces
and no real AUC was calculated in this phase.
