# V12 duplex response-clock startup and emission closure

The implementation repair and deterministic startup gates pass, but this phase does **not** close reliability qualification. The frozen 200-session public-path qualification was interrupted by loss of the foreground SSH execution session during identity 29. Per the predeclared zero-retry, stop-on-any-failure rule, identity 29 was not rerun, the remaining identities were not executed, and framework functional requalification was not started.

## Root cause and repair

The immutable slot-1 evidence supports `MULTIPLE`. The V4R5 slot-1 fixed frame completed preparation 110.974140 ms after its planned release. The release lane converted that miss into an error before the response writer, so the Relay had no successful slot-1 record. Independently, the runner counted 506 submitted requests as `emitted_cells` and used `submitted == R` as transcript completeness.

V4R6 uses one public P10 response lag for all slots: `rho = 30 ms`, derived before execution as `L_response (20 ms) + Delta (10 ms)`. The recurrence is `F_i = max(E_i + rho, gateway_arrival_i + L_response, F_(i-1) + Delta)` and `G_i = F_i - L_response`. Fixed workers cross a readiness barrier before the response clock becomes ready. A late immutable frame is written late with explicit slip/deadline-miss evidence, and subsequent releases cannot catch up. `emitted_cells` now means successful response writes. Transcript completeness additionally requires the Relay application-visible slot inventory to be exactly `1..R`.

The five frozen startup cases passed with exact 506-slot inventories: cold start, prewarmed start, a secret-independent pre-slot-1 scheduler stall, a secret-independent preparation stall across `F_1`, and a delayed Gateway request within the public bound. Related Python tests passed 65/65; the two affected Go packages passed all 49 test functions.

## Reliability stop

The first 28 synthetic public-path identities completed successfully with 506/506 release opportunities, attempts, successful writes, and Relay-visible slots. They had zero response deadline misses; the maximum release slip was 3,748,509 ns. The SSH foreground session disconnected during `DEV-DTVR-V4R6-P10-PUBLIC-PATH-R029`; that identity contains only its frozen plan/state directory and no result. It was not retried. The compressed archive in this directory preserves all 28 completed records, the execution ledger, and the partial identity-29 files.

Therefore `SYNTHETIC_RELIABILITY = FAIL (28/200 complete)`, `P10_FUNCTIONAL_REQUALIFICATION = NOT_RUN`, and `READY_FOR_NEW_DUPLEX_SMOKE = NO`. No protected classifier, AUC, P20, or P25 work ran. Timing privacy remains inconclusive.
