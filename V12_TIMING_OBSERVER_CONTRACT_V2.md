# V12 Timing Observer Contract V2

Primary roles are `REGISTRY_APPLICATION_OPERATOR` and
`RELAY_APPLICATION_OPERATOR`: honest-but-curious operators of their respective
application services. They are not Internet, packet-level, or hypervisor
observers.

Only `APPLICATION_RECEIVE_TIMESTAMP`, `APPLICATION_SEND_TIMESTAMP`,
`PUBLIC_WIRE_METADATA`, `PUBLIC_CONFIGURATION`, and
`DERIVED_FROM_ALLOWED_FIELDS` may enter TIMING_ONLY_VIEW.

## Relay

| Field | Provenance |
|---|---|
| request_observed_ns | APPLICATION_RECEIVE_TIMESTAMP |
| response_send_ns, when instrumented | APPLICATION_SEND_TIMESTAMP |
| response_observed_ns | INTERNAL_PRIVATE_STATE — excluded |
| session, round | PUBLIC_WIRE_METADATA |
| request_length, response_length | PUBLIC_WIRE_METADATA |
| profile_id | PUBLIC_CONFIGURATION |
| relative times, gaps, request-response time, total span | DERIVED_FROM_ALLOWED_FIELDS |

The historical output name `authenticated_slot_order` is retained only for
compatibility. Its provenance is public wire metadata; the name is not an
independent claim that Relay cryptographically authenticates the header.
Primary projections enforce exactly one session, chronological request and
available send timestamps, and chronological slots. Multi-session gaps are rejected.

## Registry

| Field | Provenance |
|---|---|
| request_arrival_ns | APPLICATION_RECEIVE_TIMESTAMP |
| response_send_ns, when instrumented | APPLICATION_SEND_TIMESTAMP |
| ordinal, fixed query/answer sizes and public protocol dimensions | PUBLIC_WIRE_METADATA |
| profile_id, PIR period, Q | PUBLIC_CONFIGURATION |
| relative arrivals/sends, gaps, request-response time, total span | DERIVED_FROM_ALLOWED_FIELDS |
| answer_ready_ns | INTERNAL_PRIVATE_STATE — excluded |
| executor, request_kind | INTERNAL_PRIVATE_STATE — excluded |

Tool/Agent identity, route alias, real/dummy state, operation ID, readiness,
provider/scheduler/GC/CPU/cgroup diagnostics, and newly named unknown fields are
excluded. Projection construction is an allowlist; it never copies source
dictionaries. FULL_METADATA_VIEW is outside this contract.
