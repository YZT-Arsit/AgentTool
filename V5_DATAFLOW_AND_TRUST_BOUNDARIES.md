# V5 Dataflow and Trust Boundaries

## Confidentiality boundary

The enterprise and the attested TEE/CVM are trusted. The cloud OS,
orchestrator, storage, Agent execution server, native framework workers, and
ordinary cloud-local processes are untrusted. The CommonActionGateway is trusted
only when deployed inside the enterprise/attested confidential boundary; merely
running it as another host process is insufficient.

| Data or operation | Trusted location | Forbidden ordinary-cloud exposure |
| --- | --- | --- |
| payload/session keys | TEE/CVM | key bytes, derivation state |
| prompt/private data | enterprise + TEE | plaintext, stable plaintext-derived ID |
| capability and membership result | TEE | token, route decision in STRICT |
| PIR client query generation/recovery | TEE | row index, recovered plaintext |
| Agent capsule and logical identity | TEE | capsule plaintext/hash, Agent ID |
| verifier/interpreter/private state | TEE | opcode/progress/private result |
| policy/effect authorization | TEE | rule/value and private branch |
| outbound envelope encryption | TEE/Gateway confidential boundary | provider, Tool, arguments, result |

The local implementation in `confidential_v5` is a functional backend. A
malicious host can inspect its memory. Its use does not satisfy the cloud
confidentiality theorem.

## Bootstrap and keys

```text
TEE startup
 -> measure approved runtime files/image
 -> produce attestation evidence binding measurement, challenge, ephemeral key
 -> enterprise verifies approved measurement and freshness challenge
 -> enterprise and TEE derive an ephemeral session secret
 -> HKDF domain-separates payload and transcript keys
 -> encrypted prompt/data channel begins
```

- **Measurement:** hash of the approved confidential-runtime image and policy
  manifest. The development backend hashes an explicit file manifest.
- **Ownership:** the enterprise owns policy, approved measurements, catalog
  authority, and provisioning authority. TEE-generated ephemeral private keys
  never leave the boundary under the hardware design.
- **Restart:** every boot obtains a new challenge, ephemeral key pair, boot ID,
  and session keys. Old session ciphertext is not accepted in a new session.
- **Sealed state:** AEAD binds state to measurement, domain, and epoch. The
  development backend detects corruption and caller-anchored stale epochs but
  cannot stop a malicious host from rolling back both blob and caller anchor.
- **Rotation:** rotate session keys every boot or public epoch. Rotate sealing
  roots through an enterprise-approved measurement migration procedure.
- **Rollback:** production requires a non-rollbackable monotonic counter,
  enterprise freshness service, or equivalent trusted anchor. This is not
  implemented by the local backend.

The local evidence is not hardware-signed and is rejected by default unless an
enterprise policy explicitly enables the functional backend. This prevents a
development path from silently becoming a deployment claim.

## Observer-visible data

Depending on profile, the untrusted cloud may observe profile ID, public
horizon, fixed/bucketed frame size, declared outcome class, common endpoints,
and the explicitly listed route/Tool-category leakage. It must not observe
payload, logical Agent ID, handoff target, capsule plaintext, private policy
state, Tool arguments/results, or protected destinations.

TEE placement does not hide counts, size, cadence, endpoint identity, or
resource use. Fixed transcript and CommonActionGateway mechanisms remain
necessary. Microarchitectural/cache side channels, physical attacks, malicious
CPU/firmware beyond attestation assumptions, denial of service, TEE bugs,
global traffic analysis, and confidential-GPU leakage are excluded.

## Tool placement

- `TEE_LOCAL`: executes within the attested boundary; identity can remain
  private under the profile.
- `CLOUD_LOCAL`: an ordinary named process. Its identity is visible unless it
  moves into confidential execution or behind a common confidential broker or
  Gateway.
- `EXTERNAL`: routed through the CommonActionGateway according to profile.

`STRICT` fails closed for an unbrokered sensitive `CLOUD_LOCAL` Tool. Encryption
of arguments alone does not hide the activation.
