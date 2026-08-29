# V7-OHTTP Dataflow

## Request

1. A framework adapter emits `ProtectedActionIntent`.
2. Trusted code privately selects and authenticates `AgentDescriptorV7` using
   the frozen official SimplePIR path.
3. `TrustedActionRouter` authorizes the action.
   - `AGENT_SERVICE` may use the descriptor's Agent-service route.
   - `TOOL` and `EXTERNAL_HTTP` must resolve an allowed capability through the
     trusted `ActionRouteMap`.
   - `NOOP` has no real route.
4. An RFC 9292 encoder will create a known-length request for the single
   semantic target `https://action-gateway.invalid/v1/agent-slot`.
5. Padding is chosen so the final RFC 9458 Encapsulated Request has the exact
   profile length.
6. The trusted OHTTP client creates a fresh per-slot request context.
7. The Cloud Relay forwards those exact bytes without decoding, translating,
   re-encrypting, hashing, or reconstructing them.
8. The trusted OHTTP Gateway decapsulates, validates the private schema and
   authorization, and admits at most one real action to the worker plane.

## Response

1. Provider completion is committed to the durable effect/result journal.
2. The result enters the bounded durable ready queue.
3. At a pre-existing public slot cutoff, the scheduler selects an eligible
   result despite any earlier queue entry belonging to a future session.
4. The Gateway creates a fixed padded BHTTP RESULT or WAIT response.
5. The response is encapsulated using the current slot's server context.
6. The Relay forwards the exact Encapsulated Response.
7. Trusted code decapsulates and deduplicates by private `operation_id`.

No OHTTP/BHTTP encoding or HPKE step is executed in this checkout because no
compatible audited dependency is available offline. Interfaces fail closed.

