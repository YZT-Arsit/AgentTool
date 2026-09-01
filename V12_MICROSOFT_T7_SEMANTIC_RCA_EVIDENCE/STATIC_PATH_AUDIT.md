# V12 Microsoft T7 semantic reliability static path audit

Status: `PASS`

This audit is limited to semantic/framework control flow. It does not read observer timing projections, calculate AUC, or reexecute the failed identity.

## Frozen T7 class-1 construction

`v12_timing/isolated_tasks.py:193-199` constructs the Microsoft class-1 workload as an ordinary Tool anchor followed by one Agent-as-Tool case and labels the workflow `TOOL_TO_AGENT_AS_TOOL`.

`v11_online/frameworks.py:283-330` then:

1. derives the two routed names;
2. registers the ordinary structured Tool;
3. creates the child Agent and `child.as_tool()` wrapper;
4. creates scripted function-call content through `_MicrosoftSequenceClient`;
5. enters `Agent.run()` with both tools registered.

The parent response and function-call content are created at `v11_online/frameworks.py:245-278`. Function names are resolved and invoked by the pinned framework's `FunctionInvocationLayer` in `_tools.py:1750-1879` and `_tools.py:2971-3005`. The child wrapper is constructed by `_agents.py:608-724`; the child client invokes the AgentTool implementation in `v11_full_scope/frameworks.py:360-384`.

## Why the empty executed-operation list did not mean zero invocation

The adapter appends an operation ID only after `implementation(...)` returns successfully (`v11_online/frameworks.py:300-305` and `316-321`). The pinned framework converts ordinary tool exceptions into function-result error content (`_tools.py:1573-1574` and `1640-1641`). Consequently, two invoked functions can both yield framework error results while the adapter's successful-execution list remains empty.

The preserved collector log proves exactly that sequence:

- `acv_private_route_000` was invoked and raised `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT`;
- `acv_private_route_001` was invoked through Agent-as-Tool and its child implementation raised `PIR_REAL_RESOLUTION_ADMISSION_CLOSED`.

The latest reached stage is therefore the second Agent-as-Tool child implementation, not parent invocation entry.

## Fixed-schedule failure semantics

`common_action_gateway_v2/canonicalv9/online.go:674-703` marks an accepted but undelivered operation as `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT`. `v11_online/session.py:676-683` closes cache-miss descriptor resolution at the public PIR cutoff; `v11_online/session.py:279-280` raises `PIR_REAL_RESOLUTION_ADMISSION_CLOSED` when a later uncached descriptor is requested.

This is consistent with one realized session exhausting the fixed public schedule before the first result was delivered, followed by the second descriptor resolution arriving after admission closed. It is inconsistent with a parent that simply returned without recognizing either function call.

## Microsoft framework state and name registry audit

Pinned framework commit: `af461de51da16f5cb800ff7febc0f8f96355607a`.

- `Agent.as_tool()` returns a FunctionTool bound to that child Agent; no global Agent-as-Tool registry is used (`_agents.py:608-724`).
- Agent tools are assembled for the Agent/run, with duplicate-name validation (`_agents.py:1452-1478`; `_tools.py:917-959`).
- `_get_tool_map()` rebuilds a dictionary from the tools supplied to a function-invocation attempt (`_tools.py:1644-1650`, `1750-1759`).
- `FunctionInvocationLayer` configuration is instance state (`_tools.py:3036-3059`). Budget counters are placed in a run/request context and initialized for that invocation (`_tools.py:3174-3335`).
- There is no inspected global or class-level routed-name registry that can preserve `acv_private_route_000` or `acv_private_route_001` across Agent instances.
- Duplicate routed names inside one Agent fail explicitly; they are not silently overwritten.

The repeated route-name scheme is therefore mechanically per-Agent. D5/D6 diagnostics separately test unique versus repeated per-session names.

## Async and resource audit

The preserved non-timing diagnostics contain no cancellation, file-descriptor, memory, task-leak, event-loop, or framework final-response warning associated with the abort. No such resource counters were recorded, so absence of resource pressure cannot be inferred beyond the available logs. The only recorded terminal causes are the two fixed-schedule exceptions above.

The semantic reproducer deliberately performs a fresh `asyncio.run()` and fresh parent/child Agent construction for every one of 1,200 predeclared identities, in a single long-running process, to test the relevant repetition behavior without Relay, Registry, or timing features.

## Source hashes

- `v12_timing/isolated_tasks.py`: `145127aea3cb0596d01f19d914fe789ef5258417164f4be4717507b117f8bed1`
- `v11_online/frameworks.py`: `5ba6c1070ebafcced92bebfc5e779b8c1602b14a54a861167d790ba061cb1941`
- `v11_full_scope/frameworks.py`: `b114650d8d5f4bbe0d08a3ba41e72814a46d7c3f086bc0b89c070e8cf6555d33`
- `v11_online/session.py`: `3bb4271a5ba467ea27f50e52de15c2475a00246dd53de1ed1d11be4239a7888d`
- `common_action_gateway_v2/canonicalv9/online.go`: `396f4465003ca8320a8ae831cbaf74873fd29cd6bc11e23d86701525f9bb90c5`
- pinned `_agents.py`: `362f9cc98fda41cefc7a900fa7e5900b61f21783f69349a482f8ef26f6a69bec`
- pinned `_tools.py`: `aa52744502388b1d5e734e7e5849af152bc1bf24b352041feef2d8be33731bc8`

## Interim classification before the frozen diagnostic matrix

The static evidence localizes the abort to the AgentTool session implementation and public fixed-schedule state, not to Microsoft parent function recognition or tool lookup. The frozen D1-D6 semantic matrix is required before closing intermittent adapter, Agent-as-Tool, repeated-name, and long-running-loop alternatives.
