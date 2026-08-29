# Agent / Action Route Separation V7

## Defect repaired

V6 `LocalTrustedBackend.make_action_cell` copied
`AgentDescriptorV6.gateway_route_handle` into every action cell. A Tool could
therefore inherit the selected Agent's service route. That behavior is frozen
as V6 evidence but is not canonical in V7-OHTTP.

## V7 objects

`AgentDescriptorV7` contains an optional `agent_service_route_handle` and an
allowlist of Tool/action capabilities. `ActionRouteDescriptor` separately maps
a Tool or external-HTTP capability to route handle, action class, placement,
effect semantics, and policy ID.

Resolution is:

```text
AGENT_SERVICE -> check Agent capability -> Agent service route
TOOL/EXTERNAL_HTTP -> check Agent allowlist -> trusted ActionRouteMap -> action route
NOOP -> no route and no provider work
```

The prototype route map is trusted-memory state; no additional PIR is added.

## Evidence

Five Python tests pass, including different Agent/Tool routes, unauthorized
Tool denial, action-kind mismatch denial, NOOP route absence, and fail-closed
transport status. The Go BHTTP/OHTTP contract and Relay test binary now passes
nine tests, including real loopback exact forwarding.

Status: `AGENT_TOOL_ROUTE_SEPARATION = PASS`.
