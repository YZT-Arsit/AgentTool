# PIR necessity audit

## Decision

`PIR REMOVE FROM FINAL METHOD`

1. The evaluated final architecture has no independent untrusted registry. The trusted mediator owns dispatch resolution; outsourced private records are already behind the ORAM access plane.
2. No final observer sees ordinary concrete agent-record lookups. `DIRECT` is retained only as a supporting comparison.
3. Consequently, registry-index privacy is not required by the final threat model.
4. Existing ORAM-backed state access covers the logical registry/state lookup that remains in scope.
5. PIR removes no additional host-visible leakage in the chosen architecture. It cannot hide a later visible endpoint or process activation.
6. Retaining it would add a second security definition and server-work model without protecting a distinct observer.
7. Removing PIR changes none of the Stage-12 M0--M3 results.

This does not claim PIR is ineffective in architectures with an independently untrusted registry. It is simply unnecessary here.

