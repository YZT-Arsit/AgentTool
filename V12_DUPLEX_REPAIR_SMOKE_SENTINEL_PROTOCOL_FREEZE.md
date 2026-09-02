# V12 Duplex Repair Smoke Sentinel Protocol Freeze

This phase replaces the aborted 5,040-session campaign with a fresh,
development-only repair smoke screen. Every identity from the aborted frozen
manifest remains excluded, whether or not it executed.

Five physical task/framework coordinates are frozen: C1/OpenAI, T7/OpenAI,
T7/Microsoft, T9/OpenAI, and T9/Microsoft. They produce seven observer
comparisons. Each coordinate has 32 planned TRAIN and 32 planned EVAL matched
blocks; the first 30 complete blocks in each partition are selected by a
pre-frozen priority. Total planned execution is 640 sessions, with zero retry
or replacement.

The observer projections and fixed widths are unchanged from the duplex
protocol: strengthened Relay `DUPLEX_TIMING_ONLY_VIEW` width 5,695 and Registry
`TIMING_ONLY_VIEW` width 448. Collection must be complete and hash-closed before
any classifier, AUC, bootstrap, or randomization calculation.

Analysis uses the V3.1 four-model family, grouped five-fold TRAIN-only model
selection and orientation, uint32-normalized estimator seeds, exactly one
selected EVAL model, and 10,000 complete-pair bootstrap resamples. The smoke
fails only if any comparison has one-sided LCB95 greater than 0.65. Otherwise
it may proceed to a separately authorized full duplex sentinel. A smoke pass
is not timing-privacy evidence.
