# V13 Current Agent Resolution Audit

This is an engineering audit of the runtime at
`63319014f560f46e2a46dd140f53551e43c27e0d`. It is not paper text and does
not change the frozen execution path.

## CURRENT_AGENT_RESOLUTION_FLOW

There is no explicit planner-candidate-set interface in the frozen runtime.
The nearest mechanical entry point is `CanonicalOnlineSession.submit`, which
receives a validated `V11ActionCase`; `_canonical_ids(case)` derives the
integer `agent_id`, Agent capability, action capability, and action kind at
`v11_online/session.py:1087-1115`. The integer `agent_id` is the stable
identifier bound into `AgentDescriptorV7` and its authenticated PIR row.

The V13 split-domain component is therefore a new pre-resolution abstraction:
it accepts a bounded set of those canonical integer Agent IDs. It is not wired
into `CanonicalOnlineSession` in this phase because that would modify the
frozen timing runtime.

## CURRENT_PIR_ENTRY_POINT

`OnlineSimplePIRResolver.resolve_descriptor` at
`v11_online/session.py:429-461` checks the private epoch cache and invokes
`query()` on a miss. The fixed scheduler is configured by
`CanonicalOnlineSession.__enter__` at `v11_online/session.py:1017-1039`.
The duplex scheduler commits one queued real resolution or dummy row at each
public opportunity at `v11_online/session.py:578-678`; its direct queue entry
is `query()` at `v11_online/session.py:751-766`.

The SimplePIR bridge accepts only an operation ID, row index, public ordinal,
release time, answer delay, and public period (`pir_integration/simplepir_bridge/main.go:71-78`).
The server-visible record has fixed query/answer metadata and timestamps but
not the private row index (`pir_integration/simplepir_bridge/main.go:49-63`).

## CURRENT_AGENT_DESCRIPTOR_FORMAT

`AgentDescriptorV7` contains:

- integer `agent_id`;
- canonical capability IDs;
- publisher key ID and Agent version;
- placement class;
- optional Agent-service route descriptor;
- allowed Tool capabilities;
- trust class; and
- catalog epoch.

The codec at `action_privacy_v8/descriptor.py:27-129` authenticates and pads
each descriptor to 1024 bytes, binds it to the catalog epoch, validates the
descriptor digest/version binding, and rejects a recovered row whose Agent ID
does not match the private selection.

## CURRENT_PRIVATE_SELECTION_STATE

The derived `agent_id`, descriptor cache key, real/dummy PIR choice, recovered
descriptor, route handle, and operation ID are trusted/private state. The
current cache is keyed by `(catalog_epoch, agent_id)` at
`v11_online/session.py:426-460`. The reserved dummy descriptor row is 999
(`v11_online/session.py:168-185, 490-491`).

## CURRENT_FIXED_PIR_SCHEDULE

The frozen profile defines 100 Registry opportunities at a 60 ms period over
a 6000 ms public epoch. The open-loop scheduler uses a public origin,
ordinal, period, initial lead, previous public send state, and commitment lead
only (`v11_online/session.py:106-124, 578-597`). At each cutoff it consumes an
eligible pending real resolution or the reserved dummy row, then submits the
same SimplePIR protocol request (`v11_online/session.py:598-652`). Registry
answer release remains fixed by the existing bridge's response release path.

## CURRENT_GATEWAY_HANDOFF

After PIR recovery, `CanonicalOnlineSession.submit` creates the protected
intent, resolves it through `TrustedActionRouter`, and writes exactly one
`SUBMIT_RESOLVED_ACTION` message to the already-running trusted Go session at
`v11_online/session.py:1120-1168`. Enterprise-internal execution already uses
the trusted local backend branch at `v11_online/session.py:1127-1152`; all
external resolved actions use the common Gateway session.

The new V13 abstraction preserves one common `TrustedGatewayHandoff` interface
for both enterprise-deployed and global-library descriptors. It does not add a
second public execution path.

## Existing PSI backend audit

Repository search found only `confidential_v5/membership.py`, whose
`IdealPrivateMembershipReference` is explicitly non-cryptographic. The active
Python environment contains `cryptography` but no maintained PSI, OPRF, APSI,
KKRT, or VOLE PSI package. Consequently this phase does not instantiate PSI
cryptography and does not run a PSI performance benchmark.
