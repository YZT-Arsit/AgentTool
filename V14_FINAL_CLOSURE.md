# V14 preprovisioned Agent store real PSI/PIR closure

The implementation now follows the paper's artifact-retrieval model: a
requested AgentID is resolved with real Microsoft APSI labeled PSI to a dense
SimplePIR row, the authenticated fixed record is retrieved privately, and a
real framework-native Agent is instantiated inside the trusted runtime. An
unprovisioned artifact is transported in four private chunks through the
unchanged frozen V4R8 common Gateway; it is never executed as a remote named
Agent service. No paper file or frozen V4R8 runtime source was modified.

The read-only audit found that the historical data did **not** support this
claim: the old 100K corpora were `AgentCapsule` template clones or
`AgentDescriptorV7` descriptor-only records, the 16K privacy workload used a
different 1K registry, and the historical 240-run path did not load an Agent
from the PIR result. V14 therefore generated a new 100K schema-valid synthetic
artifact corpus and states this limitation explicitly.

## Required report

```
SYSTEM_SCENARIO:
PREPROVISIONED_AGENT_ARTIFACT_STORE

RUNNING_REMOTE_AGENT_SERVICES:
NO

REAL_FUNCTIONAL_AGENT_CORPUS:
12 artifacts (6 OpenAI, 6 Microsoft); 8 executed root Agents plus 2 idle
top-level cases; 14 total PSI/PIR access slots including nested re-entry

SCALE_CORPUS:
100000

SCALE_CORPUS_REAL_WORLD_UNIQUE_AGENTS:
NO

SCALE_CORPUS_SCHEMA_VALID_ARTIFACTS:
YES; 100000/100000 authenticated, decoded, version-checked, and AgentID-bound

ARTIFACT_FORMAT:
ProvisionedAgentArtifactV1 canonical JSON + SHA-256 body binding + AES-GCM +
random padding

PIR_RECORD_BYTES:
1024

REAL_LABELED_PSI:
PASS — Microsoft APSI v0.13.1 at
548745efdb37b1d7d948c761a772488747ca16ab

PSI_LABEL:
PIR_ROW_INDEX, bound with store epoch and record version in a fixed 32-B handle

PSI_SENDER_ITEMS:
100000

REAL_SIMPLEPIR:
PASS — 14/14 real retrievals; query=36388 B, answer=37180 B

OPENAI_LOADER:
PASS

MICROSOFT_LOADER:
PASS

PROVISIONED_PATH:
PASS

UNPROVISIONED_PATH:
PASS — 1024-B artifact crossed the unchanged V4R8 Gateway in four private
chunks and authenticated after reconstruction

IDLE_PATH:
PASS

AGENT_TO_AGENT_REENTRY:
PASS — four nested top-level cases each produced two private access slots

PUBLIC_STRUCTURE_EQUIVALENCE:
PASS — provisioned, unprovisioned, and idle have identical APSI/PIR structural
wire fields and identical complete 521-cell Gateway public profiles

REMOTE_AGENT_EXECUTION:
0

PAPER_MODEL_ALIGNMENT:
PASS
```

## Exact cryptographic and structural evidence

- APSI SenderDB: 100,000 labeled items, 24,634,064 serialized bytes, 2.505 s
  preprocessing on the evaluation server.
- Thirty recorded real APSI wire-validation queries (10 hit, 10 miss, 10
  idle) each used OPRF request/response 104/104 B and query/result
  697,972/1,579,652 B with two request and two response messages.
- Fourteen real SimplePIR access slots all returned correct 1024-byte records
  with fixed 36,388-byte queries and 37,180-byte answers.
- All 10 top-level functional cases passed. OpenAI and Microsoft nested Agents
  used each SDK's real native Agent/Agent-as-Tool machinery.
- The local deterministic suite passed 10/10, including artifact tamper/ID
  binding, loader, production-guard, full 100K mapping bijection, and dummy
  namespace separation checks.
- The frozen V4R8 runner hash was
  `84fc61e363ed587ba5c200be12ebb66c9a71c69daad39950f1b50e66cd363437`.
  Provisioned cover, unprovisioned repository retrieval, and idle cover each
  completed exactly 521 public request/response cells at 1079/800 bytes.

## Claim boundary

This closes implementation, functional correctness, real cryptographic
resolution, 100K format/scale, and deterministic public-structure equality.
It is not a new privacy attack experiment and does not establish realized
timing indistinguishability. The 100K corpus is schema-valid and loadable but
is not 100K independently sourced real-world Agents.
