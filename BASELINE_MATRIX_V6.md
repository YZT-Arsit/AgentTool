# Frozen V6 baseline matrix

| ID | Path | What it isolates | Status |
|---|---|---|---|
| B0 | DIRECT_NATIVE | named endpoint/process leakage | measured local microbenchmark |
| B1 | DIRECT_TLS | payload encryption without metadata privacy | specified; not available offline as isolated TLS harness |
| B2 | PIR_ONLY then direct destination | selection privacy does not survive named activation | measured PIR components |
| B3 | COMMON_GATEWAY | destination hiding only | not isolated in this run |
| B4 | GATEWAY_FIXED_SIZE | residual count/order/timing | not isolated in this run |
| B5 | GATEWAY_FIXED_TRANSCRIPT | structural/size schedule, timing excluded | prior V5 development evidence only |
| B6 | V6_STRICT | unified PIR + trusted module + fixed Gateway | partial; live Gateway blocked/fails functional gate |
| B7 | V6_ENTERPRISE_EFFICIENT | hierarchical resolution + declared route leakage | measured-component model only |

ORAM is intentionally absent. `PERFORMANCE_RESULTS_V6.csv` distinguishes actual
measurements, component models, prior evidence, and unavailable variants.
