# Stage-6 System Architecture

## Process topology

```text
experiment driver
      |
      | length-prefixed JSON/TCP
      v
planner_process (untrusted, abstract handles only)
      |
      | protected action envelope
      v
mediator_process (one process per evaluated architecture)
      |
      +---- private_data_service --------+
      +---- permission_service ----------+---- observer/logger process
      +---- disclosure_log_service ------+     (host-visible metadata only)
      +---- unified_service -------------+
      |
      +---- mock_tool_service (authorized plaintext sink)
```

The implementation starts distinct spawned operating-system processes with
different PIDs. Every request crosses a localhost TCP socket; there are no
cross-component Python calls. The default cluster has a planner, observer, five
services, and six architecture-specific mediator processes.

## State ownership

| State | Authority | Local copies |
| --- | --- | --- |
| Private recipient/document data | PrivateData service or unified service | Materialized transiently by mediator |
| Permission | Permission service or unified service | HYBRID-P/HYBRID-PH cache after per-action validation |
| Disclosure history | Disclosure service or unified service | HYBRID-PH synchronized per-device cache |
| Tool effects | Mock tool service | None; request IDs retained for idempotency |

Hybrid data is a cache, not a transfer of authority. Authoritative remote
payload bytes are therefore the same across the protected architectures.

## Serialization and protection abstraction

Frames contain a four-byte big-endian length followed by canonical compact
JSON. Protected bodies are encoded with a deterministic local XOR/keystream and
base64 abstraction. This confines synthetic plaintext in the prototype but is
**not production encryption**. A production design would require authenticated
encryption, replay protection, key rotation, and channel authentication.

ORAM-backed responses include actual serialized JSON-safe ciphertext-padding
bytes. These bytes traverse the socket and are included in measured wire size.
The corresponding binary Path-ORAM path size is also reported separately as
`logical_oram_bytes`; JSON serialization overhead is therefore visible rather
than silently estimated.

Each RPC opens a new TCP connection. `connection_reused=false` is recorded for
every event. TCP/IP header bytes are not available at the application layer;
the accounting separates eight bytes of length framing per request/response
pair from JSON payload bytes.

## ORAM placement

- `INDEPENDENT-MODULAR-ORAM`: separately observable private, permission, and
  history endpoints.
- `FIXED-CANONICAL-MODULAR`: the same endpoints with fixed read/dummy slots and
  a fixed preflight parallel round.
- `UNIFIED-ORAM`: one endpoint, one tagged internal namespace, a batched
  preflight, and one append request. Tags exist only inside the protected body.
- Hybrids keep the private-data ORAM; HYBRID-P keeps history outsourced via
  ORAM, while HYBRID-PH synchronizes/updates history through the authoritative
  service.

This is a functional research ORAM transfer abstraction, not a production ORAM
implementation or proof.

## SEND_MESSAGE flow

1. Planner emits `SEND_MESSAGE` with `CONTACT_7` and `DOCUMENT_18` handles.
2. Mediator validates the schema and handle syntax.
3. Mediator resolves recipient and document records.
4. It reads or validates the current authoritative permission version.
5. It reads/synchronizes disclosure history in the fixed protected schedule.
6. It authorizes or denies using the returned current permission.
7. On allow, it materializes only recipient, subject, and document for the tool.
8. Mock tool applies the request ID idempotently.
9. Mediator appends the same request ID to the authoritative disclosure log.
10. Planner receives only `ALLOW`/`DENY`, sanitized effect status, and
    host-visible experimental metrics—never tool plaintext.

Private data, permission, and history preflight calls are issued in a fixed
parallel round for modular protected variants. The effect and audit append
remain ordered after authorization.

## Freshness mechanisms

HYBRID-P and HYBRID-PH send a conditional/version validation on every action.
There is no lease and therefore no intentional inter-action stale window.
HYBRID-PH additionally sends `sync(since=local_version)` on every action and
applies all missing ordered events before consulting local history. This makes
remote validation/synchronization costs explicit instead of crediting Stage-5
local memory with free authority.

## Observer view

The observer receives endpoint, public operation class, request/response byte
count, start-to-end duration, connection-reuse flag, and public logical ORAM
transfer size. It never receives protected bodies, abstract handles, plaintext
records, policy values, history branch labels, or tool arguments. Tool endpoint
identity and the fact of an authorized `SEND_MESSAGE` effect are outside the
privacy goal.

## Experimental network profiles

Application-layer servers delay each response by configured RTT plus serialized
bytes/bandwidth:

| Profile | Emulated RTT | Emulated bandwidth |
| --- | ---: | ---: |
| LOCAL-LAN | 0.5 ms | 1,000 Mb/s |
| ENTERPRISE-DC | 2 ms | 200 Mb/s |
| REMOTE-CLOUD | 20 ms | 50 Mb/s |

These are local experiment parameters, not claims about real networks. OS
scheduling, loopback copying, and JSON processing remain actual measured costs.

