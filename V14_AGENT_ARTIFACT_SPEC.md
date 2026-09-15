# ProvisionedAgentArtifactV1 specification

## Role and trust boundary

`ProvisionedAgentArtifactV1` is a declarative, loadable Agent package. The
cloud-resident Enterprise Agent Store retains only opaque fixed-size records.
The trusted runtime retrieves one row with SimplePIR, authenticates and
decrypts it, validates its `AgentID`, and constructs a real framework-native
Agent. It is not a remote Agent-service descriptor and contains no service
endpoint, route, or private execution handle.

## Canonical logical fields

- schema/artifact version and canonical non-negative integer `AgentID`;
- framework identifier (`OPENAI_AGENTS_SDK` or
  `MICROSOFT_AGENT_FRAMEWORK`);
- Agent name, instructions, and allowlisted model reference/configuration;
- allowlisted capability references;
- nested/handoff AgentIDs, which re-enter private retrieval;
- runtime policy, publisher/version, and store epoch.

The parser requires the exact field inventory. Unknown fields, unsupported
versions, stale store epochs, cyclic direct references, unknown models or
capabilities, and remote-service routing fields fail closed. Python `pickle`
and arbitrary-object deserialization are not used.

## Deterministic serialization and fixed record

The logical body is encoded as UTF-8 canonical JSON (`sort_keys=true`, compact
separators). The envelope binds the schema name and SHA-256 digest of that
canonical body. The fixed PIR record is:

```
12 B AES-GCM nonce
996 B ciphertext/plaintext area
16 B AES-GCM tag
= 1024 B
```

The 996-byte plaintext area contains a 12-byte big-endian header (`OAPA`,
version, flags, payload length), the canonical envelope, and random padding.
The AES-GCM associated data is domain-separated and binds the store epoch.
Usable canonical-envelope capacity is 984 bytes. The artifact key remains in
the trusted resolution domain and is never stored in the cloud database or
committed as evidence.

## Measured sizing decision

The 12 functional artifacts measured 819--852 plaintext bytes (median 834,
p95 850.35). The largest leaves 132 bytes of authenticated plaintext headroom,
so the mechanically selected row remains 1024 bytes. Encoding fails rather
than truncating a larger artifact. A future artifact exceeding this bound
requires a new public record-size revision or fixed-count chunking.

## Loader contract

`AgentLoader` reconstructs an actual `agents.Agent` or
`agent_framework.Agent` inside the trusted runtime. Nested Agents are loaded
first from their own authenticated artifacts and exposed using each SDK's
native `Agent.as_tool()` mechanism. The development fixtures use an
allowlisted deterministic local model; foundation-model weights are not part
of the artifact.

