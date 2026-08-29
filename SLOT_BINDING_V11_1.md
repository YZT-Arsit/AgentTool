# V11.1 public-slot binding

The outer HTTP request carries bounded public headers
`X-AgentTool-Public-Session` and `X-AgentTool-Public-Slot`.  The same pair is
encoded in the inner RFC 9292 request and response and therefore authenticated
by RFC 9458 OHTTP.  The Gateway rejects an outer/inner mismatch.  The client
rejects a response whose authenticated inner pair differs from the stream's
per-slot client context.

The Gateway maintains a mutex-protected slot registry and rejects slot 0,
slots above the profile bound, duplicate public slots, duplicate encapsulated
requests for the same slot, and invalid sessions.  It does not require wall-
clock arrival order to equal slot order.

Every request has a distinct client/server OHTTP context.  Context reuse is
rejected by an atomic one-use guard.  Response collection may be out of order,
but lookup is always by authenticated public slot; private result association
is by `operation_id`.
