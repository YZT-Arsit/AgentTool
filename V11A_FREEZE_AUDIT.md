# V11A fresh full-scope confirmatory holdout freeze audit

Status: **FREEZE COMPLETE; SELECTED EXECUTION = 0**.

- V11.4 base commit: `f6860baaab8927f9b0b66153959b55d8ca072c23`
- V11.4 exact execution-freeze SHA-256: `3d919523daac5b366b326755019f06d93caf6dd6a487ca6c75fa4c20638466c3`
- Protected implementation paths: 42/42 match the base commit.
- Master exclusions: 1074 exact source sites, 20 whole files, 59 workload signatures.
- Seed search: **NO**. All candidate universes were frozen before seed derivation.
- S1 eligible/selected: 54/32; framework balance {'OpenAI Agents SDK': 25, 'Microsoft Agent Framework': 7}.
- S2 selected: 12, by family {'OPENAI_HANDOFF': 4, 'MICROSOFT_AGENT_AS_TOOL': 4, 'OPENAI_AGENT_AS_TOOL': 4}. Microsoft handoff remains `NATIVE_MECHANISM_ABSENT`.
- S3 selected: 12, frameworks {'Microsoft Agent Framework': 6, 'OpenAI Agents SDK': 6}, families {'ALTERNATING_TOOL_SEQUENCE': 4, 'EXTERNAL_TO_INTERNAL': 1, 'AGENT_AS_TOOL_TO_TOOL': 1, 'TOOL_SEQUENCE': 3, 'STRUCTURED_TOOL_TO_AGENT_AS_TOOL': 1, 'TOOL_TO_AGENT_AS_TOOL': 2}, depths {2: 7, 10: 2, 20: 1, 30: 1, 50: 1}. Depth 30 and 50 are present.
- S4 generic effect-contract cases: 9; these are Level-A synthetic confirmatory contracts, not original source Tool semantics.
- Structural pairs: 14; internal/external, causal-depth, and Agent-service-subtype strata are present: True.
- All selected manifests loadable without runtime invocation: **PASS** (93 specifications).
- Selected semantic outcomes, trajectory outcomes, Relay traces, and privacy CSVs: **0**.

Timing privacy remains `OPEN / NOT TESTED`, packet-level timing remains `OPEN`, hardware TEE remains `NOT_TESTED`, action mediation coverage remains `894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED`, and source-body executable subset remains `0`. No overall privacy GO is issued. V11B was not run.

## Final V11A status

```text
V11_4_SYSTEM_FREEZE_VERIFIED: PASS
FINAL_PUBLIC_PROFILE_VERIFIED: PASS
CONFIRMATORY_ORCHESTRATOR_FROZEN_BEFORE_SELECTION: PASS
MASTER_EXCLUSION_SET: 1074 exact source sites / 20 whole source files / 59 workload signatures
SEED_SEARCH: NO
S1_SOURCE_TOOL_POOL: 54
S1_SOURCE_TOOL_CASES_FROZEN: 32
S1_FRAMEWORK_BALANCE: 25 OpenAI / 7 Microsoft
S2_COMPOSITION_CASES_FROZEN: 12 (4 OpenAI Agent-as-Tool / 4 OpenAI handoff / 4 Microsoft Agent-as-Tool)
S3_CAUSAL_TRAJECTORIES_FROZEN: 12 (6 OpenAI / 6 Microsoft; depth 30 and 50 present)
S4_GENERIC_EFFECT_CONTRACT_CASES_FROZEN: 9
STRUCTURAL_PAIRS_FROZEN: 14
INTERNAL_EXTERNAL_PAIR: PRESENT
CAUSAL_DEPTH_PAIR: PRESENT
AGENT_SERVICE_SUBTYPE_PAIR: PRESENT
SEMANTIC_PROJECTION_FROZEN: PASS
TRAJECTORY_PROJECTION_FROZEN: PASS
STRUCTURAL_PROJECTION_FROZEN: PASS
SIZE_PROJECTION_FROZEN: PASS
PREFIX_RULES_FROZEN: PASS
EXECUTION_ORDER_FROZEN: PASS
NO_RETRY_POLICY_FROZEN: PASS
ALL_SELECTED_MANIFESTS_LOADABLE_WITH_FROZEN_EXECUTOR: PASS
SELECTED_HOLDOUT_CASES_EXECUTED: 0
TIMING_PRIVACY: OPEN / NOT TESTED
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
READY_FOR_INDEPENDENT_V11A_AUDIT: YES
```
