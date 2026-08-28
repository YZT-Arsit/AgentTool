# Common IR and normalizer generality audit

Both runtime adapters import the same 255-line `live_core.py`. Its public configuration, slot schedule, three-access ORAM envelope, framing, approval epoch, cadence enforcement, and commit gate are unchanged across runtimes and tasks.

| Item | Result |
| --- | --- |
| IR operation/schema reuse | 100% |
| Normalizer core reuse | 100% |
| Task-specific scheduling branches | 0 LOC |
| Agent Framework adapter | 199 LOC, including profiling/CLI |
| OpenAI SDK adapter | 202 LOC, including profiling/CLI |
| Generic workload adapter | 164 LOC |

Task effect types and arguments are public data passed to the fixed commit operation. They do not select schedules. Runtime-specific code only invokes native approval/resume APIs and serializes native state. The common-core gate passes, although timing privacy does not.

