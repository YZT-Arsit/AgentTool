# Cross-task timing audit

The grouped-task evaluation holds out semantic task identifiers in four folds across the unchanged 40-task-derived corpus split. The measured phase contains 16 task identities and 192 M3 episodes per runtime.

Broad pooled receiver-arrival attacks were near chance, but cross-task generalization was not uniformly suppressed:

- OpenAI authorization send-to-receive LR: AUC 0.710, CI 0.611–0.789, p=0.020.
- OpenAI authorization receiver-processing RF: AUC 0.697, CI 0.564–0.791, p=0.020.
- Microsoft provenance release-slip RF: AUC 0.602, CI 0.527–0.719, p=0.039.

The paced-cover primitive therefore does not pass the cross-task timing gate. These are development, not confirmatory, splits; a new untouched semantic holdout is required after the mechanism and analysis are frozen.
