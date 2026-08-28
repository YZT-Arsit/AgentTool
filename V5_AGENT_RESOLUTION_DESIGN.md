# V5 Agent Resolution Design

## Trusted flow

```text
AEAD ciphertext -> TEE decrypt -> normalized private capability c
   -> membership(A_enterprise, c)
      hit  -> private index i -> real PIR row i -> verify capsule -> Control Kernel
      miss -> external discovery -> verify source/manifest -> compile -> verify capsule
```

The cloud never receives `c`, `i`, capsule plaintext, or logical Agent ID.

## Membership placement

When the complete enterprise catalog is inside the TEE, V5 uses constant-API
local membership. PSI is unnecessary. When the catalog is outsourced, the TEE
is the client of a private-set-membership/PSI/OPRF protocol and the registry is
the server. No audited offline PSI implementation was found in the current
repository, so only `IdealPrivateMembershipReference` exists to lock the API:

```text
CRYPTOGRAPHIC_PSI = NOT_IMPLEMENTED
```

It must not be used as privacy evidence.

## PIR and capsule verification

The existing pinned official SimplePIR client is the read-only registry lookup
primitive and belongs inside the hardware confidential boundary in the target
deployment. Its full-preprocessing evidence remains separate from V5. The
local functional resolver uses a `CapsuleLookup` interface; integration tests
may bind it to `SimplePIRLookupSchedule`.

Every recovered row is parsed and checked by `DeterministicCapsuleVerifier`
against an enterprise-approved manifest containing capsule digest, source path
and digest, compiler version, allowed runtime profile, and public bounds.
Classifier output is never sufficient for installation.

## Profile behavior

For `STRICT`, the public resolution projection is identical:

```text
FIXED_PRIVATE_LOOKUP -> FIXED_COMMON_GATEWAY_SLOT
```

An enterprise hit uses the real row. An external miss uses a reserved dummy row
with fresh PIR randomness, then keeps the external handle confidential. For the
two weaker profiles the route string is intentionally public and the unused
route can be omitted.

## External descriptions

External Agents are data, not trusted executable code. Only signed or
source-traceable manifests that lower to the bounded IR and pass deterministic
verification are admitted. Arbitrary callbacks, unbounded control, native
plugins, and undeclared side effects are rejected. This design does not claim a
general malicious-Agent sandbox.

## Current implementation status

| Component | Status |
| --- | --- |
| local in-TEE membership | implemented and unit-tested |
| outsourced membership API | implemented as ideal reference only |
| audited cryptographic PSI | not implemented/offline unavailable |
| real SimplePIR primitive | previously integrated; V5 adapter boundary defined |
| deterministic capsule verifier | implemented and unit-tested |
| local TEE functional backend | implemented and unit-tested |
| hardware TEE attestation | not tested |
| STRICT route-shape equality | symbolic/unit pass only |
| live TEE route privacy | open |
