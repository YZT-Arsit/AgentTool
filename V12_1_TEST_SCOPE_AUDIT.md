# V12.1 regression and environment audit

The complete repository collection contains 302 Python tests. The first Linux serial attempt produced 157 passed, 14 failed, and 9 pre-existing skips. All 14 failures were missing historical artifact or host-layout dependencies (`results_crypto_closure`, `results_timing_closure`, or Windows `.venv-stage9`), not assertions against the repaired runtime.

The Windows evidence-complete workspace then ran a mechanically frozen V12 execution-reachable collection. It collected all 302 nodes and deselected exactly one retained legacy node: `test_tool_multi_action_capacity[50]`, which exercises the superseded V10 static 111-round/5-ms profile rather than the V12 online profile. No xfail or skip was added. Result: **297 passed, 2 failed, 2 pre-existing environment skips, 1 deselected**. The two failures were `test_tool_multi_action_capacity[10]` and `test_agent_service_private_subtype_fits_existing_bucket`; both ended `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT` under Windows durable-I/O latency.

Because the serial gate was not fully green, the default full suite was not run, profile requalification was not rerun, and no holdout construction began. Linux Go tests for all packages passed, including the new WAL migration, recovery, sub-period diagnostic-slip, and crossed-deadline tests. A local Windows Go test executable was blocked by Application Control; that environment failure does not replace the Linux Go result.

This report preserves the platform distinction without converting it into PASS. The V12.1 system gate is FAIL.
