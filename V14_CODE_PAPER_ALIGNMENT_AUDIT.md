# V14 code-to-paper alignment audit

Status: **CLOSED BEFORE V14 IMPLEMENTATION**

Authoritative model: the latest five-page manuscript PDF, *OAE: Protecting
Agent Access Patterns and Execution Trajectories in Cloud-Deployed LLM Agent
Systems*, supplied as `C:/Users/hasee/Downloads/ICASSP2026 (1).pdf` (PDF
creation timestamp 2026-09-15 00:09:34 PDT), together with the user's V14
freeze. Sections 3.1, 4.1-4.3 and Fig. 1 mechanically confirm that deployed
Agents are cloud-resident artifact records retrieved with PSI+PIR, loaded and
executed inside the TEE; the Gateway mediates only communication leaving the
rented cloud; and Agent-to-Agent calls re-enter private retrieval. No paper
file was modified by this audit.

## Required paper path

The paper path is:

`AgentID -> labeled PSI -> PIRRowHandle -> SimplePIR -> AgentArtifactV1 ->
authenticated decode -> framework-native AgentLoader -> execution inside the
protected runtime`.

The Gateway is used only for communication leaving the rented cloud (Internet
Agent Repository retrieval, remote LLMs, external Tools/APIs, and enterprise
applications). It does not execute or route to a deployed Agent service.

## Mechanical code inventory

| Existing item | Source | Current semantics | V14 classification | Required action |
|---|---|---|---|---|
| `AgentDescriptorV7` | `action_privacy_v8/models.py:59` | Descriptor and placement metadata; optionally embeds `AgentServiceRouteDescriptor`. | **MODIFY** for the paper path | Preserve only as historical V4R8/V13 input. Introduce `AgentArtifactV1`; do not mutate frozen V4R8 types. |
| `AgentDescriptorV7Codec` | `action_privacy_v8/descriptor.py:27` | Canonical JSON plus AES-GCM in a fixed 1024-byte SimplePIR row. | **KEEP** for frozen V4R8; **RETIRE_FROM_AGENT_PATH** for V14 | Add a separate, versioned `AgentArtifactV1Codec` and mechanically select its row size. |
| `EnterpriseAgentRecord` | `v13_private_resolution/resolution.py:101` | Contains `private_execution_handle` and a descriptor. | **RETIRE_FROM_AGENT_PATH** | V14 sender stores only an AgentID-to-PIR-row label in APSI and opaque AgentArtifact rows in SimplePIR. |
| `private_execution_handle` | `v13_private_resolution/resolution.py:103`, `v13_private_resolution/e2e.py:129` | Private route to a remotely executed Agent service. | **RETIRE_FROM_AGENT_PATH** | Forbidden in all reachable V14 code and serialized artifacts. |
| `GatewayAgentDestination` | `v13_private_resolution/resolution.py:372` | Carries source class, descriptor, and private service handle into Gateway. | **RETIRE_FROM_AGENT_PATH** | V14 resolution returns a locally loadable authenticated artifact, not a Gateway destination. |
| `SUBMIT_RESOLVED_ACTION` | `v13_private_resolution/e2e.py:116`, `v11_online/session.py:1164` | Existing private Gateway submission ABI for external/provider actions. | **KEEP** for frozen V4R8 external actions; **RETIRE_FROM_AGENT_PATH** | Deployed Agent retrieval and local Agent invocation must not use it. |
| `REAL_AGENT_SERVICE` | `v13_private_resolution/e2e.py:133` | Sends a named Agent-service action through Gateway. | **RETIRE_FROM_AGENT_PATH** | V14 Agent path must contain zero occurrences/reachable uses. |
| Current PIR row format | `action_privacy_v8/descriptor.py:19-25,62-81`; constructed at `v11_online/session.py:197-216` | One authenticated fixed-width 1024-byte `AgentDescriptorV7`; row index is currently generated directly from `agent_id`. | **MODIFY** for V14 | Use opaque fixed-width `AgentArtifactV1` records and an explicit independently assigned `PIRRowHandle`; retain the old format only for frozen V4R8. |
| Current SimplePIR entry | `v11_online/session.py:127-216,940-949,1114-1119` | Persistent SimplePIR resolver selects a descriptor before action routing. | **KEEP** primitive and scheduler; **MODIFY** V14 adapter | Reuse the real SimplePIR wire path with V14 artifact rows and explicit row handles. |
| Current local trusted execution | `v11_online/session.py:1127-1152` | `TRUSTED_MODULE_LOCAL` executes through `LocalTrustedBackendV11`. | **KEEP** as boundary evidence | V14 provides a new framework-native loader/runtime; do not route loaded Agent execution to a cloud service. |
| OpenAI construction path | `v11_online/frameworks.py:90-214`; `v11_full_scope/frameworks.py:125-166,252-343` | Builds real `agents.Agent` objects, including `Agent.as_tool()` and handoff objects, from Python construction calls. | **MODIFY** | Capture a safe declarative construction specification in `AgentArtifactV1`, then reconstruct the real object inside the protected runtime. |
| Microsoft construction path | `v11_online/frameworks.py:284-340`; `v11_full_scope/frameworks.py:218-250,389-440` | Builds real `agent_framework.Agent` objects and `Agent.as_tool()` wrappers. | **MODIFY** | Add a Microsoft loader from the same safe declarative artifact schema. |
| V13 fixed PSI/PIR structural profile | `v13_private_resolution/resolution.py:34-88,395-415` | One PSI slot and one PIR slot, but K=8 and enterprise bound=1024. | **TEST_ONLY_LEGACY** | V14 uses one real PSI item per slot and a 100,000-record deployed-Agent store. |
| V13 mock PSI | `v13_private_resolution/resolution.py:193-241` | Plain in-process set intersection, explicitly non-cryptographic. | **TEST_ONLY_LEGACY** | It must be unreachable from V14 production/integration profiles. Real Microsoft APSI is mandatory. |

## Frozen components that remain unchanged

- V4R8 timing runtime and public parameters (`H=4500 ms`, `B=200 ms`,
  `Delta=10 ms`, `M=50`, `R=521`, `Q=100`, response clock and Registry clock).
- Existing OHTTP/BHTTP frame sizes and observers.
- Existing SimplePIR cryptographic implementation and trusted Gateway external
  communication channel.
- Historical V13/V13B code and evidence, retained only for reproducibility and
  excluded from the V14 paper path.

## V14 implementation decisions frozen by the audit

1. `AgentID` is a non-negative integer below the reserved dummy namespace.
2. APSI receiver cardinality is exactly one. Idle slots query a domain-separated
   dummy item using the real APSI protocol.
3. The labeled-PSI value is a fixed-width `PIRRowHandle` binding row, store epoch,
   and artifact record version; it contains no route or execution endpoint.
4. PIR row order is independent of AgentID. The mapping is authenticated by the
   APSI label and rechecked against the decoded artifact's AgentID.
5. `AgentArtifactV1` is deterministic canonical JSON protected with AES-GCM and
   padded to one measured fixed row width. Pickle and arbitrary code loading are
   forbidden.
6. The loader uses an allowlisted declarative framework construction schema.
   It creates framework-native Agent objects inside the trusted runtime.
7. Deployed, undeployed, and idle slots all execute one real APSI query and one
   real SimplePIR query. The undeployed artifact is retrieved through the common
   Gateway repository operation, then passed to the same local loader.
8. Nested Agent references are AgentIDs and re-enter the private retrieval
   pipeline; no Agent-specific connection is created.

## Stop conditions

V14 must fail closed if Microsoft APSI labeled mode cannot carry the row-handle
label, if the supported artifacts do not fit a justified fixed row, if the
SimplePIR database cannot hold 100,000 fixed artifact records, if APSI wire
structure cannot be normalized across hit/miss/idle, or if any reachable V14
path invokes a remote Agent service.
