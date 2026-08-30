# V12-FINAL System Gate

`V12_SYSTEM_GATE = FAIL`.

## Reachability closure

The actual selected V12 path is frozen as:

`run_v12_confirmatory -> v11a_confirmatory.orchestrator -> CanonicalOnlineSession -> OnlineSimplePIRResolver -> acv-simplepir-online`.

It does not call the historical `cryptographic_closure.pir_backend.run_simplepir` or `go run .` path. With Go deliberately absent from the process PATH, the frozen prebuilt bridge completed one direct DEV PIR query and one actual online canonical action: 1/1 PASS. The prebuilt bridge SHA-256 is `2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b`.

The separate V10.1 compatibility path was run once with Go 1.26.5 prepended only to that subprocess PATH and passed 11/11. This does not change the V12 selected-runtime dependency contract or reinterpret V12.3.

## Current-runtime failure

The frozen 70-node current-runtime serial gate produced 69 PASS and 1 FAIL. The failing actual-path node was `test_actual_v12_online_multi_action_causal`.

Two DEV actions used distinct operation IDs but the same logical Tool name, `v11_tool_0`. OpenAI emitted a Tool-name collision warning. Both calls produced outcomes, but both dispatched through the same registered Tool identity, so `outcomes_by_operation` contained only one operation ID and the online causal integrity assertion failed.

This is an actual V12-path defect, not a historical Go/PIR compatibility failure. The result was not retried or repaired after observation. Therefore the default Class-A gate, Go gate, profile requalification, B4/B5 performance, affected security cells, and holdout construction were not run.

## Final state

- V12.3 failure preserved: PASS
- Actual V12 runtime reachability audited: PASS
- Historical go-run PIR used by V12: NO
- Prebuilt PIR with Go removed from PATH: PASS
- Legacy V10.1 compatibility: 11/11
- Current-runtime Class-A serial: 69/70 FAIL
- Current-runtime Class-A default: NOT RUN
- Linux Go tests: NOT RUN
- Profile requalification: NOT RUN
- Post-repair B4/B5: NOT RUN
- Candidate universe/seed/selected manifests/execution plan: not created
- Selected V12 cases executed: 0
- `results_v12_confirmatory`: absent
- Ready for independent V12 final freeze audit: NO

Timing privacy remains OPEN / NOT TESTED. Packet-level timing remains OPEN. Hardware TEE remains NOT_TESTED. Source-body executable subset remains 0.
