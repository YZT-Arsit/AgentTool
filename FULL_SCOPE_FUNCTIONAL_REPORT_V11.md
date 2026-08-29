# Full-scope functional report V11

Run-2 result: **6/7 gates passed**. The 1-action run had a provider result durably committed but not delivered after a ~737 ms first-round stall exceeded the frozen 555 ms session. The same gate passed in the pytest development suite, while 10 and 50 actions passed in run 2. This is preserved as intermittent controlled-host/session-budget instability, so MULTI_ACTION is PARTIAL rather than promoted to PASS.

| gate | functional | admitted | delivered | dummy_provider_operations | profile_overflow_events | error |
| --- | --- | --- | --- | --- | --- | --- |
| TOOL_1 | False | 1 | 0 | 0 | 0 |  |
| TOOL_10 | True | 10 | 10 | 0 | 0 |  |
| TOOL_50 | True | 50 | 50 | 0 | 0 |  |
| EXTERNAL_HTTP | True | 1 | 1 | 0 | 0 |  |
| DIRECT_AGENT_SERVICE | True | 1 | 1 | 0 | 0 |  |
| TRUSTED_MODULE_LOCAL_AGENT | True | 1 | 1 | 0 | 0 |  |
| CONTROLLED_COMPLETION_BEHAVIOR | True | 2 | 2 | 0 | 0 |  |
