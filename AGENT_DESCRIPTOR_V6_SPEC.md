# AgentDescriptorV6 specification

Every physical PIR row is exactly 1,024 bytes:

```text
12-byte random nonce || AES-GCM(ciphertext over 996-byte padded plaintext)
```

The authenticated plaintext contains `ATD6`, schema version 6, logical Agent
ID, capability IDs, publisher key ID, Agent version, placement class, opaque
Gateway route handle, runtime metadata, allowed Tool capability IDs, trust
class, catalog epoch, and a canonical descriptor digest. Random padding fills
the fixed row.

AEAD associated data domain-separates `AgentTool|AgentDescriptorV6|epoch`.
Recovery rejects tag failure, schema mismatch, digest mismatch, stale epoch,
malformed versions, and mismatch between the expected private Agent ID and the
decrypted descriptor. Control IR and executable Python are forbidden.

The current local format uses AEAD authentication rather than a separately
verifiable publisher signature. A production multi-publisher catalog would
need signed descriptor provenance in addition to catalog encryption.
