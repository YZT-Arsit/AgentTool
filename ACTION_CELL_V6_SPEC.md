# ActionCellV6 specification

`ProtectedActionIntent` carries a private capability, protected argument bytes,
session ID, operation ID, and action class from an orthogonal protected payload
pipeline.

Inside the trusted module it becomes a 1,024-byte `ActionCellV6`:

```text
12-byte random nonce || AES-GCM(fixed 996-byte padded action record)
```

Private fields are REAL/NOOP or Tool/Agent-service/HTTP class, opaque route
handle, protected arguments, operation ID, and continuation state. Associated
data binds the public profile and slot. Unit tests verify fixed width, AEAD
tamper rejection, slot binding, and absence of route/capability plaintext.

The public boundary sees only profile, slot, 1,024-byte ciphertext, and
`CommonActionGatewayV2`. Dummy cells never create provider work or effects.
