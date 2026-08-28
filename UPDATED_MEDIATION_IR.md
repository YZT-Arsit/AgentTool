# Updated Mediation IR

## Design choice

Stage 11 extends rather than replaces the Stage-9/10 IR. The existing authorization/provenance program and `AdaptiveNormalizer` remain the downstream core. A minimal routing front end supplies a semantic capability and an authorized agent envelope.

Implementation: [ir.py](stage11_core_redesign/ir.py).

## Operations and annotations

| Operation | Default visibility | Effect boundary | Purpose |
|---|---|---:|---|
| `PARSE_INTENT` | PUBLIC projection | No | Parse only the declared public task projection |
| `SELECT_CAPABILITY` | PUBLIC/allowed | No | Produce semantic capability/opaque handle |
| `RESOLVE_AGENT` | PRIVATE | No | Map capability plus private policy/configuration to concrete index |
| `FETCH_AGENT_RECORD` | PRIVATE | No | Retrieve descriptor/credential handle using direct, PIR, or ORAM registry access |
| `AUTHORIZE_AGENT` | PRIVATE | No | Validate selected specialist and delegated authority |
| `PREPARE_DISPATCH` | PRIVATE | No | Build authenticated real/cover envelope set |
| `DISPATCH_AGENT` | PRIVATE to protected observer | No | Deliver specialist request; agent work itself is not the external tool effect |
| `RESOLVE` / private-object resolution | PRIVATE | No | Existing Stage-9 operation |
| `AUTHORIZE` | PRIVATE | No | Existing permission evaluation |
| `CHECK_PROVENANCE` | PRIVATE | No | Existing history/provenance check |
| `REQUEST_LOCAL_CONSENT` | PRIVATE | No | Real trusted prompt only when required |
| `PERSIST_AUTHORIZATION` | PRIVATE | No | Existing approval persistence |
| `REBUILD/PERSIST_PROVENANCE` | PRIVATE | No | Existing provenance path |
| `VERIFY_AUTHORIZATION` | PRIVATE | No | Existing revalidation |
| `PREPARE_EFFECT` | PRIVATE | No | Bind real authorized effect to commit token |
| `COMMIT_EFFECT` | PUBLIC projection | **Yes** | Only operation allowed to create the external effect |
| `RETURN_SANITIZED` | PUBLIC projection | No | Release class-consistent result |

## Values

Private annotations:

```text
concrete_agent_id
registry_index
authorization_exists
provenance_state
approval_occurrence
retry_resume_count
real_or_cover_slot
```

Public annotations:

```text
public_task_projection
semantic capability class
runtime/configuration
H, Delta, B, W
public outcome class
complete public effect projection
```

The semantic capability is public only for the main formulation. A deployment that treats capability as private needs a different leakage class and private routing computation; it cannot reuse this theorem unchanged.

## Compilation boundary

```text
planner adapter
  -> SELECT_CAPABILITY(h)
trusted routing adapter
  -> RESOLVE_AGENT / FETCH_AGENT_RECORD / AUTHORIZE_AGENT
dispatch adapter
  -> fixed public dispatch schedule
unchanged Stage-9 program
  -> AdaptiveNormalizer.compile(program, H)
M3 transport adapter
  -> fixed B, Delta, W
trusted effect gate
  -> one COMMIT_EFFECT at public slot
```

Framework-specific adapters map native approval/interruption events into the shared IR. They do not author schedules or branch on experiment labels.

## Generality status

```text
Same downstream IR across Microsoft + OpenAI runtimes: PASS
Same downstream normalizer: PASS
Routing front end task-name hardcoding: ABSENT
Live routing adapter in either public runtime: NOT IMPLEMENTED
M3 live transport enforcement: NOT IMPLEMENTED
```

This is a controlled IR extension, not a new general-purpose oblivious compiler.
