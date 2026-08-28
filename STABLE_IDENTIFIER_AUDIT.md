# Stable Identifier Audit

| Field | Classification | Finding |
|---|---|---|
| `SimplePIRServer` identity | `PUBLIC_STABLE` | Common physical server, independent of target |
| query/answer dimensions and bytes | `PUBLIC_STABLE` | Determined by public database/profile |
| query ordinal / public slot | `PUBLIC_STABLE` | Sequence counter, not target-derived |
| raw PIR query and query digest | `FRESH_RANDOMIZED` | Different for repeated target queries |
| PIR client seed/randomness | `SECRET` | Client-side upstream PRG state |
| selected index / Agent name | `SECRET` | Private trace only |
| recovered capsule and logical ID | `SECRET` | Client/private control plane only |
| fixed control frame | `PUBLIC_STABLE` | Same common ABI and serialized width |
| `AgentControlExecutor` identity | `PUBLIC_STABLE` | Same for all logical Agents |
| protected Tool ciphertext | `FRESH_RANDOMIZED` | Fresh AES-GCM nonce per envelope |
| `CommonToolExecutor` endpoint | `PUBLIC_STABLE` | Common endpoint for every action slot |
| logical Tool handle / Tool class | `SECRET` | Decrypted only at the common boundary |
| session/episode labels | `SECRET` | Ground-truth artifacts only |
| target-derived mailbox/cache/workflow IDs | `FORBIDDEN_STABLE_TARGET_DERIVED` | None present in final host artifacts |

`FORBIDDEN_STABLE_TARGET_DERIVED` findings: **zero** in the evaluated candidate trace.

The audit searched candidate Python code and serialized host artifacts for capsule hashes, logical IDs, Agent/Tool
names, deterministic encrypted capsules, mailbox IDs, workflow IDs, cache keys, and target-derived correlation IDs.
Timing remains a non-identifier side channel and is not reclassified as a pseudonym.
