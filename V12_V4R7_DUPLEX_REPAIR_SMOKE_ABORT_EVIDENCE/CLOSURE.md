# V12 V4R7 duplex repair smoke closure

The development smoke is `NOT_EVALUABLE`. Collection stopped after the first frozen identity and before any classifier fit, AUC, bootstrap, randomization, selected-block construction, or class-conditioned timing summary.

The pre-execution gates passed: the execution source was exactly `cbeef543400cd4b9f35c1b7bac6d8a167234c75f`, the protected-runtime diff from `06bb4677fe51defb8823a1fcaf685856cda15845` was empty, 32/32 deterministic tests passed, both runner binaries matched the qualified V4R7 hashes, and all 640 B40000-series identities were disjoint from 35,115 recorded development identities.

The first identity was not reexecuted. Its application runtime completed all 521 public cells: 521 response-release opportunities, 521 attempts, 521 successful writes, 521 Relay application receipts, exact unique slot set 1 through 521, and `public_transcript_complete=true`. It recorded two response deadline misses with no infrastructure-liveness failure.

The frozen collector nevertheless required zero Gateway response deadline misses and classified the session as a common integrity failure. That gate is incompatible with the V4R7 late-frame contract and this phase's explicit rule that scheduler slip is not an integrity failure when the committed frame is emitted and the transcript is complete. The root cause is therefore `COLLECTION_HARNESS_LATE_FRAME_CONTRACT_DEFECT`, not a protected-runtime failure.

Because the execution-source and analysis hashes were frozen and one identity had already been consumed, the harness was not repaired in place and collection was not resumed. All 640 identities remain permanent development exclusions. No timing result or historical-vs-V4R7 ablation was computed.
