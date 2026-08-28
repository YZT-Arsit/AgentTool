# Offline IR classifier report

## Dataset discipline

The compile-time classifier uses 4,374 high-confidence gold instances only:
3,574 existing `COMPILED`/`SHARED_PRIMITIVE` positives and 800 audited
`ARBITRARY_CALLBACK_OR_RUNTIME` negatives after key deduplication. All
MIXED/UNPROVEN, structured-candidate, and extractor-artifact rows are excluded
from training labels. Source-file grouped splits prevent same-file leakage.

Features are local source context, API/behavior tokens, framework, and file AST
counts. No model or dependency was downloaded.

## Results

Across three file-grouped seeds, mean macro-F1 was 0.9990 for logistic
regression, 0.9996 for calibrated linear SVM, and 0.9981 for random forest/SVD.
At the conservative `P(LOWERABLE) >= 0.9` acceptance threshold, all three had
zero false accepts on these grouped splits, with mean abstention 3.29%, 0.26%,
and 15.79% respectively.

Cross-framework transfer is materially weaker: macro-F1 ranges from 0.666 to
0.974. The worst observed false-accept rate at the 0.9 threshold is **2.586%**.
This is the security-relevant result: the classifier is not safe as an
authorization mechanism.

The very high within-framework scores are partly explained by strong API and
behavior-family regularities in the audited labels. They are a proposal-ranking
baseline, not semantic support. Every proposal still requires deterministic
verification, source mapping, and differential semantic testing. Coverage
change claimed: **none**.
