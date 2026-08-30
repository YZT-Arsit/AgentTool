# V12-RC invocation-routing root cause

V12-FINAL remains a permanent **FAIL**. Its 69/70 Class-A result and the failed
`test_actual_v12_online_multi_action_causal` evidence are not rerun, overwritten,
or reinterpreted.

The defect was an identity-layer conflation in `v11_online/frameworks.py`.
`logical_action_name` served both as the paper-facing semantic Tool identity and
as the framework registry/dispatch key. Two operations with distinct operation
IDs but the same logical name (`v11_tool_0`) were registered and called under one
framework name. OpenAI reported a Tool-name collision and resolved both calls
through the same registered callable closure. Both calls returned, but the
operation-specific outcome map lacked one expected operation ID.

V12-RC separates the identities:

- `logical_action_name` remains the original semantic identity and may repeat.
- `acv_private_route_NNN` is an injective, per-registry dispatch alias.
- The alias is created before Agent construction and is used only by framework
  registration and scripted framework calls.
- Dispatch closures still receive the original `V11ActionCase`; outcome
  attribution is keyed by its original operation ID.
- Exact `Counter` equality is required for expected, executed, and mapped
  operation IDs.
- The private alias is forbidden from semantic projections, provider-visible
  requests, Relay traces, structural projections, and size projections.

The repair is generic across ordinary Tool, Agent-as-Tool, sequential,
parallel-capable, and mixed framework registries. It does not reject repeated
logical Tools, rename paper-facing actions, synthesize outcomes, or change the
public profile.
