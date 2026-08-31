# V12 non-timing Python regression gate

The predeclared 220-node serial gate ran once on the authorized Linux instance. It produced **198 passed, 13 failed, 9 skipped**, with three timing-dependent nodes deselected before execution. The gate is **FAIL**. The default-mode gate was not run after that decisive failure; it is not a retry mechanism.

The failures are preserved without post-outcome reclassification: two current Agent-IR action-as-tool assertions failed, one current partial-session cleanup fixture no longer matches the three-argument provider constructor, nine tests could not find frozen historical evidence files in the Linux bundle, and one Stage-9 test requires a Windows `Scripts/python.exe` layout. The nine Stage-10 skips also remain in the denominator and therefore independently prevent a 100% PASS.

This failure does not erase the independently passing component tests, but it prevents `NON_TIMING_SOFTWARE_CLOSURE = PASS`.
