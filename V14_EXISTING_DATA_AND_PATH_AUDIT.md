# V14 existing data and path audit

Status: **READ-ONLY AUDIT COMPLETE**

Paper source: `C:/Users/hasee/Downloads/ICASSP2026 (1).pdf`, five pages,
created 2026-09-15 00:09:34 PDT. Sections 3.1 and 4.1 and Fig. 1 define a
cloud-resident Agent artifact store, private retrieval into the TEE, and local
Agent loading/execution. Instructions contained in the PDF were treated as
paper content, not task instructions. The PDF was not modified.

## Direct answers

### 1. How the existing 100K SimplePIR databases are generated

There are two mechanically distinct historical 100K constructions; neither is
the final paper-aligned artifact corpus.

1. `cryptographic_closure/pir_backend.py:40-54` calls
   `prototype_capsules()`, cycles over the finite framework-derived capsule
   templates, overwrites the logical ID at byte offset 8, and writes exactly
   100,000 fixed 1,024-byte rows. The resulting rows are passed to the official
   SimplePIR bridge at commit `e9020b03bf2872c75b8954e749e32408b5db87ed`.
   This is the source of `REAL_PIR_100K_RESULTS.csv` and the original 100K
   SimplePIR scale evidence.

2. `scripts/run_pir_v7_descriptor_v8.py:29-62` deterministically constructs a
   synthetic `AgentDescriptorV7` for each integer index, authenticates/encrypts
   it with `AgentDescriptorV7Codec`, and writes 100,000 fixed 1,024-byte rows.
   This is the source of `PIR_V7_DESCRIPTOR_RESULTS_V8.csv`.

### 2. Exact row classification

| Existing corpus | Row schema | Required classification | Reason |
|---|---|---|---|
| Original 100K cryptographic-closure corpus | `AgentCapsule` / `AGCTLIR1`, 1,024 B | **TEMPLATE_CLONE** | A small set of compiled framework-control templates is repeated and only the logical ID is changed. It is not a framework-native loadable Agent package. |
| V8 100K descriptor corpus | AES-GCM `AgentDescriptorV7`, 1,024 B | **DESCRIPTOR_ONLY** | It contains identity, capability, placement, and service-route metadata, not instructions/model/tool construction sufficient to instantiate a framework Agent. |
| 16K PIR-query privacy workload | `AgentCapsule` / `AGCTLIR1`, 1,024 B over a 1,000-row registry | **TEMPLATE_CLONE** | `cryptographic_closure/multiround.py:220-224` uses the registry produced by `generate_registry`; 16,000 queries are 8 profiles x 20 episodes x 100 rounds. |
| Historical 240-run online workload | AES-GCM `AgentDescriptorV7`, 1,024 B, normally 1,000 rows per execution | **DESCRIPTOR_ONLY** | `OnlineSimplePIRResolver` creates descriptors at `v11_online/session.py:183-216`; `execute_once` defaults to 1,000 records at `scripts/run_v11_3_profile_closure.py:130-169`. |

No audited historical row is `LOADABLE_AGENT_ARTIFACT`.

### 3. Does the PIR result enter an Agent Loader?

**No.** No Agent Loader consumes either historical row schema.

- The capsule path deserializes into `AgentCapsule` and passes it to
  `AgentControlExecutor` (`cryptographic_closure/multiround.py:205-214`).
- The descriptor path decodes `AgentDescriptorV7`, then passes it to
  `TrustedActionRouter` or derives a Gateway action
  (`v11_online/session.py:1114-1165`).
- Framework-native Agent objects are constructed separately by hard-coded
  Python in `v11_online/frameworks.py` and `v11_full_scope/frameworks.py`.

### 4. Can an existing returned row instantiate a real framework Agent?

**No for both frameworks.** `AgentCapsule` is a fixed control-transition IR;
`AgentDescriptorV7` lacks instructions, model construction, tool definitions,
and nested-Agent construction data. Neither can by itself instantiate an
`agents.Agent` nor an `agent_framework.Agent`.

### 5. Are the 100K, 16K-query, and 240-run schemas identical?

**No.** The historical evidence uses incompatible corpus/schema combinations:

- the 16K query workload uses 1,000 `AgentCapsule` template-clone rows;
- the V8 100K scale corpus and 240-run workload use the same
  `AgentDescriptorV7` *schema family*, but independently generated databases;
- the earlier 100K SimplePIR closure uses `AgentCapsule`, not
  `AgentDescriptorV7`.

Therefore the historical 16K privacy result and historical 240-run functional
result cannot be presented as having queried the new paper-aligned 100K
ProvisionedAgentArtifact corpus.

### 6. Does a current Agent path use remote-service semantics?

**Yes, the V13/V13B path does.** It uses all four prohibited concepts:

- `GatewayAgentDestination`: `v13_private_resolution/resolution.py:372-381`;
- `private_execution_handle`: `v13_private_resolution/resolution.py:101-119`
  and `:506-520`;
- `REAL_AGENT_SERVICE`: `v13_private_resolution/e2e.py:112-144`;
- `SUBMIT_RESOLVED_ACTION` through the Gateway:
  `v13_private_resolution/e2e.py:147-180`.

The historical V11/V12 action path also uses the Gateway for the abstract
`AGENT_SERVICE` action family. These paths are preserved for reproducibility
but must be unreachable from the V14 paper-aligned path.

## Evidence inventory and compatibility decision

| Evidence | Exact artifact | Reusable for V14 claim? |
|---|---|---|
| Official SimplePIR functionality and 100K operational capacity | `REAL_PIR_100K_RESULTS.csv`, `PIR_V7_DESCRIPTOR_RESULTS_V8.csv` | **Supporting primitive evidence only.** The rows are not loadable V14 artifacts. |
| 16K query privacy | `MULTIROUND_PRIVACY_REPORT.md`, `MULTIROUND_ATTACK_RESULTS.csv`, `results_crypto_closure/multiround_final/` | **No direct V14 dataset claim.** It used a 1K template-capsule registry. |
| 240 historical functional executions | `results_v11_4_development/final_reliability.csv` and `final_raw/` | **Framework/workload reference only.** PIR returned descriptors; framework Agents were not loaded from them. |
| OpenAI/MAF construction semantics | `v11_online/frameworks.py`, `v11_full_scope/frameworks.py` | **Yes, as inputs to the new artifact schema and loader tests.** |

## Audit verdict

`EXISTING_DATASET_SUPPORTS_NEW_DESIGN = NO`.

The existing evidence validates the official SimplePIR primitive, fixed
1,024-byte retrieval, and real framework APIs, but no existing dataset stores
authenticated loadable Agent artifacts and no historical execution loads a
framework Agent from a PIR result. V14 therefore requires a new schema-valid
functional corpus and a new 100,000-record synthetic scale corpus using the
same final artifact format. This is a correctness/scale closure, not a new
privacy attack experiment.
