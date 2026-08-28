# Agent control virtualization architecture

```text
trusted selector
      |
      v
PrivateAgentLookup(index)       current backend: NON-CRYPTOGRAPHIC MOCK
      |
      v
fixed 1,024-byte Agent capsule  logical identity is protected data
      |
      v
AgentControlExecutor.step(...)  one common physical entry point
      |
      v
fixed 4-slot / 1,024-byte ABI   structural and serialized-size profile
      |
      v
shared LLM or Tool adapter      exactly one real heavy operation in prototype
```

`HANDOFF(j)` updates the private logical Agent identifier and continues through
`AgentControlExecutor`; it does not start a named process, issue an Agent-specific
RPC, or use an Agent-specific URL. Tool identity is protected only up to the
common `ToolExecutionAdapter`. An observer of the ultimate external destination
is outside this prototype's demonstrated boundary.

The current fixed transcript uses nominal cadence metadata. It establishes
structural and actual serialized-size equality only; it does not establish live
timing privacy.
