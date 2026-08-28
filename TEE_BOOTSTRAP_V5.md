# TEE bootstrap V5

1. Start the approved confidential image and generate an ephemeral X25519 key.
2. Measure the runtime image/manifest and bind measurement, enterprise challenge,
   monotonic issue time, and ephemeral public key into attestation evidence.
3. Enterprise policy checks the measurement allow-list, challenge, platform
   certificate chain, TCB/SVN, and revocation status.
4. Only after successful verification, derive payload/transcript keys with
   X25519 and HKDF-SHA256 and open the encrypted prompt/data channel.
5. Rotate ephemeral keys at every boot/public epoch. Reject old-session frames.
6. Seal checkpoints with measurement/domain/epoch binding. Require an external
   non-rollbackable freshness anchor before accepting production restoration.

The local backend implements the data flow with standard `cryptography`
X25519/HKDF/AES-GCM, but its evidence is not hardware signed. It is rejected by
default unless policy explicitly opts into functional development.

```text
HARDWARE_TEE_ATTESTATION = NOT_TESTED
SEALED_STATE_INTEGRITY = FUNCTIONAL_PASS
SEALED_STATE_ROLLBACK_WITHOUT_EXTERNAL_ANCHOR = NOT_PROTECTED
```
