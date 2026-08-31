# V12 framework iteration-bound privacy audit

This audit was completed before the fresh native and live-capacity gates.

## Microsoft Agent Framework

The old adapter inherited the pinned default `max_iterations=40`. The pinned public API permits a constructor-supplied `FunctionInvocationConfiguration`. The repaired adapter supplies the same public values to every Microsoft parent sequence client:

- `max_iterations=50`
- `max_function_calls=50`

The values are derived only from public `M=50`. Agent identity, Tool identity, repeated/rare naming, Agent-as-Tool use, and actual action count do not influence them. The mediation adapter rejects a 51st real operation before framework execution, so the larger framework completion budget does not enlarge system capacity.

## OpenAI Agents SDK

The pinned SDK defines a turn as one AI invocation, including tool calls. The ordinary path previously supplied `max(10, len(cases)+2)`, so its bound encoded private trajectory length and could affect native termination. This cannot be treated as entirely private in a timing-oriented design.

All current top-level OpenAI runs and nested Agent-as-Tool runs now receive the fixed public value `OPENAI_NATIVE_MAX_TURNS_PUBLIC=M+2=52`. The minimum sequential requirement is 51 invocations for 50 one-call turns plus a final response; the single public slack turn preserves the prior development margin without depending on secret depth. Handoff and Agent-as-Tool paths receive the same top-level bound.

These controls affect only private native framework execution. They do not modify public periods, PIR schedule, Relay transcript count/size, OHTTP/BHTTP, provider-visible logical requests, or semantic/structural projections.
