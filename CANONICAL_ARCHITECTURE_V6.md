# Canonical V6 architecture

V6 narrows the system to action-metadata privacy. It assumes an orthogonal
protected-payload pipeline and does not protect prompts, model internals, or
chain of thought.

```text
ProtectedActionIntent
  -> LocalTrustedBackend (future attested TEE/CVM)
     capability -> private Agent ID
  -> official SimplePIR over encrypted AgentDescriptorV6 rows
  -> authenticated descriptor recovery inside trusted module
  -> fixed encrypted ActionCellV6
  -> opaque cloud slot client (no key or private workload)
  -> CommonActionGateway V2 persistent TCP tunnel
  -> trusted route-handle resolution
  -> exactly the requested local/external provider action
```

`CANONICAL_IR_DEPENDENCY = NONE`. Agent Control IR, its compiler, and its
interpreter are historical/optional sandbox research, not dependencies of
selection, mediation, Gateway framing, or V6 security claims.

The local trusted backend is functional evidence only. Hardware TEE
attestation and hostile-host memory confidentiality are not tested. The live
Gateway V6 matrix was blocked by Windows Application Control after one
development arm; that arm also delivered only 43/50 results. Consequently the
canonical composition is implemented through the Gateway wire boundary but is
not a completed live end-to-end validation.

ORAM is not in this graph. It remains an optional outsourced-private-state
extension only.
