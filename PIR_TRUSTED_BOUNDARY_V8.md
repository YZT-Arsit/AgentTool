# SimplePIR Trusted Boundary V8

The canonical API is modeled as:

```text
TrustedPIRClient.prepare_query(private Agent ID)
  -> opaque query bytes + private recovery context

UntrustedPIRServer.answer(opaque query bytes)
  -> opaque answer bytes

TrustedPIRClient.recover(private context, opaque answer)
  -> encrypted AgentDescriptorV7 row

TrustedActionModule authenticates row
  -> AgentDescriptorV7 plaintext
```

Trusted state includes private Agent ID, SimplePIR shared/client state and hint,
fresh query randomness, query generation, answer recovery, descriptor key, and
descriptor plaintext. Server state includes the encrypted-row database, public
parameters, and opaque query/answer messages.

The pinned bridge maps these semantics to upstream `Query`, the portable
server matrix-vector answer, and client recovery. The local measurement harness
runs both roles in one process for instrumentation; its traces and APIs are
logically separated, but this is not deployment process isolation. Server logs
contain query dimensions/bytes/digest, answer bytes/time, and executor only.

Official SimplePIR source remains pinned at
`e9020b03bf2872c75b8954e749e32408b5db87ed`; its cryptography was not modified.

