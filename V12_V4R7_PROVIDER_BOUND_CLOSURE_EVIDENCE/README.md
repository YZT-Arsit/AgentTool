# V12 V4R7 Provider Bound Closure Evidence

This directory preserves the pre-outcome provider measurement result, exact execution-source and binary hashes, the full compressed 200-session synthetic reliability archive, its ledger and summary, and the compressed fresh functional requalification evidence.

The synthetic reliability gate passed 200/200 with zero retries. Functional requalification stopped at its first genuine failure: OpenAI `CAUSAL_DEPTH_50`, the seventh executed unit. The preceding six OpenAI units passed, including `CACHE_REUSE_30`. The failed session retained a complete 521-cell duplex public transcript and 100-query Registry schedule, but only 39/50 causal operations completed before the fixed H4500 admission horizon; 11 later resolved actions were not admitted. All 39 admitted provider diagnostics were `PROVIDER_OK`.

No protected classifier, AUC, P20, P25, or privacy smoke was run. Microsoft `CACHE_REUSE_30` was not reached because the frozen first-failure rule stopped the matrix.

Archive hashes:

- `synthetic_reliability_records.tar.gz`: `a9c456cdb71347f899fe92d635351ddf989adcf664db588539e750f951b79057`
- `functional_requalification_records.tar.gz`: `8c57d71866824480b33a23deef0396e4809747fed531257e046b09dba50c9504`
