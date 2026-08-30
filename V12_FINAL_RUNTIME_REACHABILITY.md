# V12 Final Runtime Reachability

The selected V12 path is `scripts.run_v12_confirmatory -> v11a_confirmatory.orchestrator -> CanonicalOnlineSession -> OnlineSimplePIRResolver -> acv-simplepir-online`.

On Linux the online resolver uses the frozen prebuilt bridge and fails closed if it is absent. It imports only `SIMPLEPIR_COMMIT` from the historical PIR module; neither the orchestrator nor online session references or calls `run_simplepir`. Go and GCC discovery are build/legacy concerns, not selected-runtime dependencies.

The separate V10.1 compatibility path is `run_canonical_case -> CanonicalSemanticBridge -> real_pir_select -> run_simplepir -> go run .`. Its PATH/toolchain requirement remains valid legacy regression evidence but is not reachable from selected V12 execution.

All source files, sizes, call edges, and assertions are frozen in the JSON companion before decisive V12-FINAL execution.
