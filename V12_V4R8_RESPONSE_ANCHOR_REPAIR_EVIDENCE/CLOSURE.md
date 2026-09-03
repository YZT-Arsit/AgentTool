# V12 V4R8 response public-anchor repair closure

This phase made one targeted post-outcome development change: the planned Gateway response release is now anchored only to the frozen public request eligibility and prior planned public release.

```text
OLD: F_i = max(E_i + rho, gateway_request_arrival_i + L_response,
               F_(i-1) + Delta)
NEW: F_1 = E_1 + rho
     F_i = max(E_i + rho, F_(i-1) + Delta)
```

Gateway request arrival remains recorded and observer-visible where allowed, but no longer changes `F_i`, `G_i`, or a later planned response deadline. The physical no-catch-up envelope remains `S_i = max(F_i, S_(i-1) + Delta)`.

## Frozen public profile

- V4R8, H=4500 ms, B=200 ms, Delta=10 ms, M=50
- rho=30 ms, response preparation lead=20 ms
- R=521, Q=100
- request=1079 bytes, response=800 bytes
- utility parameters, observer features, and statistical protocol: unchanged

## Deterministic and deployment gates

- V4R8-specific Go tests: 5/5 PASS
- full `canonicalv9` Go package: 49/49 PASS
- V4R8 Python tests: 6/6 PASS
- deployment: 326/326 files, 11/11 module probes, 2/2 binaries, PASS

## Collection

The fresh, pre-frozen campaign executed 640/640 identities with zero retry or replacement. It closed with 638 COMPLETE and two isolated `T9/OpenAI/class1` semantic-completion failures. Sixty-two complete blocks remained for that coordinate, so the frozen first-30 TRAIN and first-30 EVAL selections were evaluable. Collection-time classifier, AUC, bootstrap, and randomization counts were all zero.

## Development smoke result

| Task | Framework | Observer | Selected model | TRAIN dist. AUC | EVAL AUC | CI95 | LCB95 | Rand. p | Smoke fail |
|---|---|---|---|---:|---:|---|---:|---:|---|
| C1 | OpenAI | Registry | HGB | 0.6222 | 0.5556 | [0.4122, 0.6956] | 0.4367 | 0.2180 | No |
| T7 | OpenAI | Registry | HGB | 0.6133 | 0.5689 | [0.4111, 0.7222] | 0.4378 | 0.1866 | No |
| T7 | OpenAI | Relay | HGB | 0.5822 | 0.4556 | [0.2978, 0.6211] | 0.3211 | 0.7101 | No |
| T7 | Microsoft | Registry | RBF SVM | 0.6456 | 0.5567 | [0.4244, 0.6933] | 0.4444 | 0.2051 | No |
| T7 | Microsoft | Relay | HGB | 0.6711 | 0.4267 | [0.2767, 0.5767] | 0.3011 | 0.8394 | No |
| T9 | OpenAI | Relay | HGB | 0.8389 | 0.8244 | [0.6711, 0.9511] | 0.6989 | 0.000400 | **Yes** |
| T9 | Microsoft | Relay | Extra Trees | 0.5900 | 0.4467 | [0.3222, 0.5744] | 0.3411 | 0.7887 | No |

The frozen smoke rule is triggered because `T9 / OpenAI / Relay` has LCB95 0.6989 > 0.65.

```text
V4R8_DUPLEX_REPAIR_SMOKE = FAIL_SUBSTANTIAL_RESIDUAL_DISTINGUISHABILITY
READY_FOR_FULL_DUPLEX_SENTINEL = NO
TIMING_PRIVACY = INCONCLUSIVE
TIMING_GO = NO
```

## Development-only Relay ablation

| Comparison | Historical one-sided P10 | V4R7 | V4R8 |
|---|---:|---:|---:|
| T7 / OpenAI / Relay | 0.9808 | 0.4856 | 0.4556 |
| T7 / Microsoft / Relay | 0.9693 | 0.6711 | 0.4267 |
| T9 / OpenAI / Relay | 0.9780 | 0.6844 | 0.8244 |
| T9 / Microsoft / Relay | 0.9903 | 0.4689 | 0.4467 |

These independent datasets are not pooled. This is development ablation only, not confirmatory evidence.

## Analysis execution audit

Two mechanical pre-fit failures and one SSH interruption were preserved append-only. The interruption occurred after TRAIN fits but before any result file or AUC exposure. The final run used the identical frozen dataset, selected blocks, seed manifest, features, models, and thresholds under a persistent worker. No protected session was reexecuted.

P10 full, P20, P25, confirmatory, and final holdout were not run.
