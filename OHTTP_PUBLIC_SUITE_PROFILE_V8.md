# OHTTP Public Suite Profile V8

V8 separates three concepts:

1. RFC Gateway Key Configuration: key ID, KEM, public key, and one or more
   allowed KDF/AEAD combinations.
2. Selected public request suite: key ID, KEM, KDF, and AEAD.
3. Deployment metadata: authenticated source and rotation/config epoch.

Key ID and suite identifiers are allowed public Relay leakage. Config epoch is
deployment/profile metadata, not asserted to be an RFC wire field.

`ScheduleProfile` and `RelayPublicEvent` carry the selected public key ID,
KEM/KDF/AEAD IDs, and config epoch. No concrete suite or public key is frozen in
`PUBLIC_PROFILE_V8.json` because the OHTTP source gate is blocked and actual
encapsulated-size expansion is unknown. Illustrative unit-test values are not
deployment claims.

