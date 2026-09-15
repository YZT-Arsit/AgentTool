# V15B pipelined Agent-access profile redesign closure

## Decision

`V15B_DECISION = PROFILE_REDESIGN_PASS`.

Persistent real Microsoft APSI and SimplePIR services, combined with a fixed
one-stage public pipeline, reduce median complete slot work from the V15A
sequential 129.003 ms to 58.673 ms.
The selected public profile is P2: `R_A=4`, `Delta_A=350 ms`, and a 1425 ms
Agent-access horizon including the 25 ms initial lead and completion envelope.
It admits at most three early-eligible requests and guarantees serial retrieval
depth two. Capacity overflow is explicit and fail-closed.

## Exact report

- `BASE_V15A_COMMIT`: `6a04a67b6c54b8a01ca2a38a17247a486e420430`
- `PSI_BACKEND`: Microsoft APSI v0.13.1
- `PIR_BACKEND`: SimplePIR
- `CRYPTO_SERVICES_PERSISTENT`: YES
- `PER_SLOT_PROCESS_STARTUP`: NO
- `PIPELINED_PSI_PIR`: PASS
- `PIPELINE_FIXED_ONE_SLOT_OFFSET`: PASS
- `PSI_STAGE_P50`: 54.194359 ms
- `PSI_STAGE_P95`: 65.071187 ms
- `PSI_STAGE_P99`: 74.182479 ms
- `PIR_STAGE_P50`: 57.104382 ms
- `PIR_STAGE_P95`: 66.560432 ms
- `PIR_STAGE_P99`: 89.075438 ms
- `MAX_TESTED_SUSTAINABLE_SLOT_RATE`: 8.0 slots/s (125 ms; 1000/1000, not a future-host guarantee)
- `SAFE_DELTA_A`: 350 ms
- `WORKLOAD_AGENT_ACCESS_MEDIAN`: 1.5
- `WORKLOAD_AGENT_ACCESS_P95`: 2
- `WORKLOAD_AGENT_ACCESS_MAX`: 2
- `WORKLOAD_MAX_CAUSAL_DEPTH`: 2
- `SELECTED_R_A`: 4 public slots
- `SELECTED_DELTA_A`: 350 ms
- `SELECTED_AGENT_ACCESS_HORIZON`: 1425 ms
- `SELECTED_PROFILE_BYTES_SESSION`: 10,384,559 total public bytes (9,405,600 Agent-access + 978,959 frozen Gateway)
- `SELECTED_PROFILE_MAX_AGENT_ACCESSES`: 3
- `FULL_SESSION_SCHEDULE`: PASS
- `STRUCTURAL_EQUIVALENCE`: PASS
- `GATEWAY_PROFILE_CHANGED`: NO
- `NEW_PRIVACY_ATTACK_EXPERIMENTS`: 0
- `PAPER_FILES_MODIFIED`: NO
- `V15B_DECISION`: PROFILE_REDESIGN_PASS

## Scope boundary

This closure establishes throughput feasibility and exact non-timing structural
equivalence for the selected public profile. It does not run or replace any
privacy classifier and does not establish realized timing indistinguishability.
