# V12 timing transitive runtime manifest

Status: **PASS**.

The final pre-live manifest contains 696 exact-byte bindings. It starts at `scripts/run_v12_timing_development.py` and includes the capacity-only driver, all statically reachable local Python modules, both complete pinned framework source packages, canonical Go build inputs, the vendored OHTTP tree, all tracked SimplePIR source/build inputs, timing profiles, projections, attack code, and protocol/matrix files.

The final manifest SHA-256 is `0d77200c7bcc26faad5e93458fce0e5647ea3b1786c2eaaa2306aff40f883061`. The Linux host matched 696/696 source artifacts, 10/10 actual imported `module.__file__` paths, and 2/2 actual executable binaries. Git metadata was unavailable on that deployment directory, so the exact transitive artifact manifest is the deployed-source identity. This is stronger than hashing a separate checkout because the verifier hashes the files actually imported and the binaries actually resolved.

The previous stale deployment is not erased or regraded. Its mismatch remains the root cause of `ABORTED_HARNESS_INTEGRITY_FAILURE_BEFORE_ATTACK_SESSIONS`.
