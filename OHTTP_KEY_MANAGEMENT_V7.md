# OHTTP Key Management V7

## Required configuration

The canonical client pins an authenticated Gateway Key Configuration containing
key ID, KEM ID, KDF ID, AEAD ID, Gateway public key, creation/rotation epoch,
and authenticated source. The Gateway alone owns the matching HPKE private key.
The Cloud Relay never receives it.

## Local research mode

Once an RFC backend is vendored, local experiments may use a generated Gateway
key pair and a pinned configuration file inside trusted experiment state. The
private key must be written only to the Gateway's private configuration and
excluded from Relay logs/artifacts. Test keys must be ephemeral and explicitly
marked synthetic.

## Rotation and restart

- A public rotation epoch selects an authenticated key configuration.
- New slots use the current configuration; an in-flight unary exchange retains
  its own context until its response is processed.
- Restarts reload current and explicitly permitted overlap keys from trusted
  Gateway state.
- Stale/unknown key IDs fail closed; application `operation_id` deduplication
  remains separate from OHTTP replay handling.

## Current boundary

The schema is implemented in the transport contract, but no HPKE key is
generated or provisioned because the RFC backend is absent. Attestation-to-key
binding and hardware TEE attestation are separate and `NOT_TESTED`.

