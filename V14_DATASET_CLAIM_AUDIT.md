# V14 dataset claim audit

| Evidence/corpus | Size actually used | Row schema | Real or synthetic | Loadable | Purpose and permitted claim |
|---|---:|---|---|---|---|
| Historical original SimplePIR scale | 100,000 rows | `AgentCapsule/AGCTLIR1` template clones | Synthetic template clones | No framework Agent | Supporting historical SimplePIR scale only; not V14 artifacts. |
| Historical V8 descriptor scale | 100,000 rows | encrypted `AgentDescriptorV7` | Synthetic descriptors | No | Descriptor-PIR scale only. |
| Historical PIR linking/privacy workload | 16,000 real queries over a 1,000-row registry | `AgentCapsule/AGCTLIR1` | Synthetic templates | No | Existing linking evidence. It did **not** query the 100K V14 database. |
| Historical end-to-end workload | 240 executions, normally 1,000 descriptor rows per execution | `AgentDescriptorV7` | Synthetic descriptors plus real SDK execution harnesses | Descriptor itself: no | Historical functionality only; the returned descriptor did not construct the Agent. |
| V14 functional Agent corpus | 12 artifacts; 10 top-level cases, including 8 executed Agents and 2 idle cases | `ProvisionedAgentArtifactV1` | Deterministic benchmark Agents derived from the real OpenAI/MAF construction paths | Yes | Loader and two-tier semantic correctness. Four nested cases generated 14 total private access slots. |
| V14 scale corpus | 100,000 artifact rows plus one reserved dummy row | authenticated encrypted `ProvisionedAgentArtifactV1`, 1024 B | Schema-valid synthetic template corpus | Yes under the allowlisted loader schema | A 100,000-record provisioned-Agent store using the production artifact format. Not 100K independently sourced real-world Agents. |
| V14 real labeled PSI | 100,000 sender items; 30 recorded wire-validation queries plus 14 functional access slots | `AgentID -> 32 B PIRRowHandle` | Real Microsoft APSI cryptography | N/A | Real private address resolution and hit/miss/idle structural equality. Not a classifier experiment. |
| V14 real SimplePIR | 100,001 physical rows; 14 recorded functional retrievals | 100,000 artifact records plus one dummy row | Real SimplePIR protocol | Retrieved real rows: yes | Artifact retrieval and fixed PIR wire shape. Not the historical 16K privacy campaign. |

## Claim decisions

- `100,000-record provisioned-Agent store using the same authenticated artifact
  format as the functional workloads`: **DIRECTLY_SUPPORTED**.
- `100,000 unique real-world Agents`: **NOT_SUPPORTED** and prohibited.
- `16,000 PIR queries over the V14 100K artifact store`: **NOT_SUPPORTED**;
  the 16K workload used a different 1K template-capsule registry.
- `historical 240 runs loaded Agents from PIR artifacts`: **NOT_SUPPORTED**;
  those PIR rows were descriptors and the SDK Agent was constructed elsewhere.
- `V14 timing privacy`: **NOT_EVALUATED**. Structural equality excludes timing.

The full read-only source audit is in `V14_EXISTING_DATA_AND_PATH_AUDIT.md`.

