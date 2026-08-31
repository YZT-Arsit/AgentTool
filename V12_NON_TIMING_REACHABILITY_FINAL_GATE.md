# V12 non-timing reachability closure — final decision

The prior a7c58e phase remains `FAIL` with 198 passed, 13 failed, and 9 skipped. Nothing in that result was regraded.

The current reachability audit is PASS and mechanically shows Agent-IR V2 is not used by selected V12 execution. Its historical Agent-as-Tool failures remain `FAIL 0/2` under legacy compatibility. The actual native routing path passed 15/15 with fresh identities after separately preserving a 9/15 new-test-assertion precheck.

The cleanup failure was a stale fixture against the correct two-argument production provider API. Its direct cleanup/resource regression passed. Serial current-runtime Python passed 46/46 with zero skips. However, the required default-mode gate failed at collection because the pytest console entrypoint lacked the repository import path. It was not replaced or retried. Therefore:

```text
CURRENT_NON_TIMING_SOFTWARE_CLOSURE = FAIL
LEGACY_COMPATIBILITY_STATUS = FAIL_PRESERVED
```

Go remains 70/70. Security negatives remain 22/22, with the two routing-related cases revalidated. No timing work, candidate universe, seed, selected manifest, authorization, or selected execution occurred.
