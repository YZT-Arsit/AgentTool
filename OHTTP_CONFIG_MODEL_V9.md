# OHTTP Configuration Model — V9

Status: **IMPLEMENTED FOR DEVELOPMENT**

Three objects remain distinct:

1. RFC Gateway Key Configuration: `key_id`, `KEM`, public key, and supported
   `(KDF, AEAD)` suites, serialized by the upstream implementation.
2. Selected public request suite: `key_id`, `KEM`, `KDF`, and `AEAD`, bound by
   `PublicSuite` and validated before Gateway cryptographic processing.
3. Deployment metadata: configuration epoch and authenticated source. These are
   deliberately not serialized as RFC Gateway Key Configuration fields.

Development tests use public key ID 7, DHKEM(X25519, HKDF-SHA256) `0x0020`,
HKDF-SHA256 `0x0001`, AES-128-GCM `0x0001`, and configuration epoch 3. These
values are test metadata, not yet a frozen canonical public experiment profile.

