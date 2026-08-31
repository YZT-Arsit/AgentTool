# V12 non-timing closure — final gate

`NON_TIMING_SOFTWARE_CLOSURE = FAIL`.

The new server is another quota-limited, non-isolated Docker execution boundary. It lacks an exclusive cpuset, IRQ exclusion, real-time scheduling authority, and a controlled CPU-frequency policy. It is therefore not materially stronger than the failed VM; no new period was tested and timing remains a core but open claim.

Independent component evidence is strong but does not satisfy the aggregate gate:

- private routing: FAIL overall; the V12-RC routed-identity repair remains PASS, but two broader Agent-as-Tool IR regressions fail;
- provider diagnostics: PASS, with the historical provider error still unresolved;
- effect/recovery: PASS;
- real prebuilt SimplePIR runtime without Go in `PATH`: PASS;
- OHTTP/BHTTP: PASS;
- frozen non-timing security negatives: 22/22;
- frozen non-timing Go tests: 70/70;
- frozen non-timing Python serial gate: **198/220 passed, 13 failed, 9 skipped**.

Because the Python prerequisite failed, default mode was not run as a replacement. The failures include two current Agent-IR semantic assertions and one current cleanup-fixture mismatch, as well as an incomplete historical-evidence bundle and a Windows-specific historical runtime path. They are preserved exactly; none was reclassified after its outcome.

The action corpus remains 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED. The fresh official-sample audit is partial because one declared Microsoft source path is unavailable; the historical 53/28/4 static matrix remains preserved, not regenerated.

B0-B3 remain 1/14, 2/14, 11/14, and 13/14. Final B4/B5 evidence is deferred until a qualified timing platform/profile exists. No candidate universe, seed, selected manifest, authorization, execution plan, or confirmatory result directory was created.

`READY_FOR_TIMING_PLATFORM_QUALIFICATION = NO` on the available instance, and `READY_FOR_V12_FINAL_HOLDOUT = NO`.
