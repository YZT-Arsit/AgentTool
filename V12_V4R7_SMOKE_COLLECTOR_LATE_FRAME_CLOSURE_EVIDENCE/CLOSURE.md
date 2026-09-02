# V12 V4R7 smoke collector late-frame closure

This is development-only timing repair evidence. It does not establish timing privacy.

## Closure

```text
BASE_ABORT: 6be7408113583323e6c249c0ab881344b6a61235
ROOT_CAUSE: COLLECTION_HARNESS_LATE_FRAME_CONTRACT_DEFECT
PROTECTED_RUNTIME_DIFF: NONE
OBSERVER_FEATURE_DIFF: NONE
STATISTICAL_PROTOCOL_DIFF: NONE
STRUCTURAL_REPLAY: PASS
COLLECTOR_DETERMINISTIC_TESTS: 6/6 collector contract PASS; 1/1 smoke freeze PASS; 2/2 analysis binding PASS

PLANNED_FRESH_SESSIONS: 640
EXECUTED_FRESH_SESSIONS: 640
RETRIES: 0
COMPLETE_SESSIONS: 640
FAILED_SESSIONS: 0
TOTAL_ALLOWED_RESPONSE_DEADLINE_MISSES: 13
MAX_RESPONSE_RELEASE_SLIP_NS: 139089337

DUPLEX_REPAIR_SMOKE: PASS_TO_FULL_SENTINEL
READY_FOR_FULL_DUPLEX_SENTINEL: YES
TIMING_PRIVACY: INCONCLUSIVE
TIMING_GO: NO
```

The collector now treats a response deadline miss as a retained diagnostic when the committed frame is eventually written and the complete public inventory remains valid. Missing/duplicate slots, failed writes, incomplete strengthened observer boundaries, inconsistent transcript accounting, and actual no-catch-up violations still fail closed.

Collection closed before analysis with 640/640 identities, zero failures, zero retries, and zero classifier/AUC/bootstrap runs during collection. All five physical coordinates supplied 32 complete TRAIN and 32 complete EVAL matched blocks; the frozen priority selected exactly 30/30. A pre-fit namespace-binding defect initially applied the shared 315/180/120 denominator instead of the smoke's frozen 64/30/30 denominator. That attempt stopped before any model fit or AUC. The narrow binding repair changed no data, priorities, features, seeds, models, hyperparameters, or statistical rules.

## Observer comparisons

| Task | Framework | Observer | TRAIN-selected model | TRAIN dist. AUC | EVAL AUC | 95% CI | LCB95 | Randomization p | Smoke failure |
|---|---|---|---|---:|---:|---|---:|---:|---|
| C1 | OpenAI | Registry | RBF SVM | 0.6761 | 0.5489 | [0.4289, 0.6700] | 0.4478 | 0.2050 | No |
| T7 | OpenAI | Registry | HistGradientBoosting | 0.6756 | 0.4344 | [0.2789, 0.5956] | 0.3022 | 0.7815 | No |
| T7 | OpenAI | Relay | LogisticRegression | 0.6456 | 0.4856 | [0.3344, 0.6400] | 0.3578 | 0.5748 | No |
| T7 | Microsoft | Registry | RBF SVM | 0.5433 | 0.4311 | [0.3122, 0.5500] | 0.3300 | 0.8629 | No |
| T7 | Microsoft | Relay | HistGradientBoosting | 0.7067 | 0.6711 | [0.5367, 0.7911] | 0.5589 | 0.00970 | No |
| T9 | OpenAI | Relay | ExtraTrees | 0.5689 | 0.6844 | [0.5378, 0.8178] | 0.5622 | 0.01320 | No |
| T9 | Microsoft | Relay | HistGradientBoosting | 0.5944 | 0.4689 | [0.3189, 0.6233] | 0.3433 | 0.6577 | No |

No comparison crossed the predeclared repair-smoke failure rule `LCB95 > 0.65`. The two highest point estimates remain development signals and require the authorized full sentinel; smoke passage is not a privacy verdict.

The 640 raw session records are preserved in `collection/session_records.tgz`; `collection/dataset_manifest.json` records each identity and record hash. `SHA256SUMS.txt` covers the transferred evidence artifacts.
