# V12 Microsoft native depth API audit

This audit was frozen before native boundary execution. The pinned implementation is `external_stage9/agent-framework/python/packages/core/agent_framework/_tools.py` at SHA-256 `aa52744502388b1d5e734e7e5849af152bc1bf24b352041feef2d8be33731bc8`.

The pinned public API supports the required override. `FunctionInvocationConfiguration` is publicly exported by `agent_framework`; `FunctionInvocationLayer.__init__` accepts `function_invocation_configuration`, normalizes it, and exposes it as `function_invocation_configuration`. The pinned source itself demonstrates setting `client.function_invocation_configuration["max_iterations"]` and `max_function_calls`.

`max_iterations` counts LLM roundtrips, not individual functions. The initial model request is iteration one. A response containing multiple function calls consumes one iteration while each call contributes to `max_function_calls`. If all iterations request functions, the non-streaming loop performs one final tools-disabled model response after the iteration loop; that final response does not consume another `max_iterations` unit.

For the public system bound `M=50` and the development client's one sequential function call per model response, the minimum supported public value is therefore `MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC=50`. Iterations 1 through 50 execute the 50 operations and the pinned phase-three path obtains the final framework response. `max_function_calls` is also fixed at 50. Both values are public-profile constants and do not depend on the workflow's actual private length.

No Microsoft source was changed. No constant was monkeypatched, no private framework state was mutated, and the native `Agent.run` path remains in use.
