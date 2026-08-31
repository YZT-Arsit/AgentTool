# V12 MDCC fresh live-capacity audit

The frozen six-workload campaign started exactly once on the hash-verified Linux deployment. It stopped at the first failure, as predeclared. No workload was retried or replaced.

The first identity was `DEV-MDCC-OA-SAME-AGENT-DEPTH50-001`. Its native OpenAI execution completed all 50 intended operations; the subsequent canonical execution completed only 46 before the remaining four intents were resolved after the public admission horizon. The first missing operation was index 46 (the 47th operation), `op7317990911e13f1ec0f093a397f1`.

The canonical public session itself was `COMPLETE`, emitted `356/356` cells, and retained a complete fixed-size public transcript. It recorded 46 admitted operations, 46 provider invocations, 46 results, four `resolved_not_admitted_ids`, zero pending operations, zero profile overflow, zero silent committed-result loss, zero dummy-heavy provider operations, and no infrastructure liveness flag. The public scheduler recorded 236 missed deadlines; maximum launch slip was 30.622045 ms on the unisolated host. The four late operations were:

- `op7317990911e13f1ec0f093a397f1`
- `opb668676f1fe16227517abfc65066`
- `op5249c879daa4ce316efd428a04d8`
- `op3e706dbfd138bca425bbe3ed4915`

PIR mechanics remained exact in the failed workload: 100 fixed queries, one real resolution, 99 dummy queries, 49 trusted descriptor cache hits, fresh query hashes, and the prebuilt SimplePIR binary. Thus this observation is not a Microsoft iteration failure and does not mechanically invalidate the K6/PIR60/EPOCH6000/Q100 PIR-cover construction. It does invalidate this phase's integrated live-capacity gate because the action/PIR/framework workflow did not deliver all 50 operations under the current host run.

The Microsoft depth-50 live workload and the other four frozen workloads were not executed. Timing attack sessions and timing confirmatory sessions remained zero.
