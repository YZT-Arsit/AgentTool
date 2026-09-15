# V14 dataset construction

## Functional corpus

The functional corpus contains 12 `ProvisionedAgentArtifactV1` objects:
six OpenAI Agents SDK artifacts and six Microsoft Agent Framework artifacts.
For each framework it contains a provisioned ordinary Agent, provisioned
nested parent and child, and corresponding unprovisioned repository ordinary,
nested parent, and child artifacts. These are deterministic benchmark Agents
that instantiate real framework classes; they are not claimed to be
independently collected real-world Agents.

Six provisioned functional artifacts are embedded in the Enterprise Agent
Store. Six unprovisioned functional artifacts are held by the development
Internet Agent Repository adapter and cross the frozen Gateway artifact path
when requested.

## Scale corpus

The scale corpus contains exactly 100,000 authenticated, schema-valid Agent
artifact records using the same encoder, AEAD envelope, 1024-byte row, and
loader schema as the functional corpus. The remaining scale records are
deterministically varied template artifacts: AgentID, framework, name, role,
expected output, and non-security-critical metadata vary, while the
construction vocabulary is intentionally bounded. This supports a
100,000-record store-scale claim, not a claim of 100,000 independently sourced
or behaviorally unique real-world Agents.

Generation alternates the two framework identifiers and cycles 16 documented
template roles per framework. A fresh AEAD nonce and random row padding are
used for every encoding. After construction, all 100,000 rows were read back,
authenticated, parsed, version-checked, and bound to their expected AgentID.
The resulting database SHA-256 was
`dbb1982bcfb72aa550cf7017565f1122619769cbbfbc7d695cf95d2a0220d3975`.

The real SimplePIR file contains these 100,000 artifact rows plus one reserved
opaque dummy row (100,001 physical rows total). The real APSI SenderDB contains
exactly 100,000 `AgentID -> PIRRowHandle` labeled entries. The large generated
database and private development AEAD key are intentionally not committed;
they are regenerable from the source harness, while the exact run hash and
validation counts are preserved in `V14_DATASET_RESULTS.json`.

## Construction and validation entry point

`scripts/run_v14_preprovisioned_agent_closure.py` performs corpus generation,
full-row validation, APSI preprocessing, real APSI/SimplePIR execution, and
framework loading. No attack classifier, AUC, timing privacy experiment, or
paper modification is part of this workload.

