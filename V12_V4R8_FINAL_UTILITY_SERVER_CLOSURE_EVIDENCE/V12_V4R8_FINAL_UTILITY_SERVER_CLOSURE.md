# V12 V4R8 Final Utility and Server Closure

The frozen V4R8 runtime source is `63319014f560f46e2a46dd140f53551e43c27e0d` and the protected-runtime diff is `NONE`. This phase ran no timing-security experiment, classifier, AUC, bootstrap, or randomization analysis.

## Utility benchmark

The frozen benchmark executed 480/480 measured runs with zero retries: Native 240 successes and 0 failures; OAE V4R8 233 successes and 7 semantic failures. The full failed-session archive shows that all 7 failed semantic runs nevertheless completed their 521-cell/100-query public transcripts, with zero silent loss, profile overflow, or infrastructure-liveness failure.

- OpenAI Agents SDK / ORDINARY_TOOL: Native median/p95 11.884/15.793 ms; V4R8 semantic median/p95 426.631/497.664 ms; public-session median/p95 6099.722/6117.785 ms; overhead +414.746 ms / 35.899x.
- OpenAI Agents SDK / AGENT_AS_TOOL_TRANSITION: Native median/p95 19.851/21.829 ms; V4R8 semantic median/p95 609.495/1142.536 ms; public-session median/p95 6099.826/6112.888 ms; overhead +589.644 ms / 30.703x.
- OpenAI Agents SDK / CACHE_REUSE_30: Native median/p95 206.471/227.361 ms; V4R8 semantic median/p95 2094.690/2268.272 ms; public-session median/p95 6096.457/6178.751 ms; overhead +1888.218 ms / 10.145x.
- OpenAI Agents SDK / CAPACITY_50: Native median/p95 121.847/128.335 ms; V4R8 semantic median/p95 1003.317/1385.216 ms; public-session median/p95 6107.324/6205.419 ms; overhead +881.470 ms / 8.234x.
- Microsoft Agent Framework / ORDINARY_TOOL: Native median/p95 6.448/7.397 ms; V4R8 semantic median/p95 421.943/521.989 ms; public-session median/p95 6094.684/6111.960 ms; overhead +415.495 ms / 65.436x.
- Microsoft Agent Framework / AGENT_AS_TOOL_TRANSITION: Native median/p95 8.997/10.023 ms; V4R8 semantic median/p95 572.177/743.657 ms; public-session median/p95 6100.800/6124.679 ms; overhead +563.179 ms / 63.593x.
- Microsoft Agent Framework / CACHE_REUSE_30: Native median/p95 59.407/74.788 ms; V4R8 semantic median/p95 1631.077/1817.158 ms; public-session median/p95 6095.468/6155.989 ms; overhead +1571.671 ms / 27.456x.
- Microsoft Agent Framework / CAPACITY_50: Native median/p95 86.724/194.732 ms; V4R8 semantic median/p95 954.625/1615.972 ms; public-session median/p95 6101.672/6198.801 ms; overhead +867.901 ms / 11.008x.

## Communication and PIR

The final profile uses 521 Relay cells and 100 Registry queries. It carries 978959 Relay bytes plus 861200 Registry bytes, for 1840159 bytes (1.754912 MiB) per normalized session. Relay and Registry schedules overlap.

PIR utility is inventory-only: the 100,000-record scale run contains 10 correct queries, while the separate repeated-observation run contains 16,000 correct queries over 1,000 records. No new PIR campaign ran, and no unavailable metric was fabricated.

## Termination decision

`SAFE_TO_TERMINATE_SERVER = YES` at closure generation. `SERVER_ONLY_ESSENTIAL = NO`; low-level duplicate execution directories are not paper-bearing after the per-run records, summaries, environment snapshot, and hashes are committed. No server shutdown, reboot, suspend, or deletion was performed.
