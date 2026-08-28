# Cross-Runtime Comparison

| Property | Microsoft Agent Framework | Runtime 2: OpenAI Agents SDK |
|---|---|---|
| Private state | Standing approval rule present/absent in session state | Per-call approval decision present/absent in `RunState` / `RunContextWrapper` |
| Native mediation operation | `ToolApprovalMiddleware` standing-rule check and approval request | `needs_approval` evaluation, `ToolApprovalItem` interruption, `RunState.approve`, runner resume |
| Adaptive branch | Missing rule returns an approval request and requires a second application invocation | Missing decision re-interrupts and requires a second measured `Runner.run` continuation |
| Same initial public task | YES | YES |
| Same final effect | YES; identical local share effect once | YES; identical synthetic `send_message` effect once |
| Natural trajectory distinction | 1 versus 2 application invocations | 1 versus 2 runner invocations; 0 versus 1 interruption |
| Per-action mitigation sufficient? | NO | NO |
| Adaptive mitigation result | H=5 structural view equal; AUC 0.500 | H=5 structural view equal; AUC 0.500 |
| Dummy external effects | 0 | 0 |
| Upstream semantic patches | None | None |

## Shared abstraction

The common abstraction is not a coincidental API detail:

```text
private mediation state
    -> native approval lookup
    -> optional approval interruption/persistence
    -> resume/reinvoke
    -> same real public effect once
```

The frameworks store the decision at different granularity: Microsoft Agent Framework uses a standing session rule, while OpenAI Agents SDK can store a decision for the exact pending call and also supports sticky decisions. Both nonetheless expose the same security-relevant transition: stored authority suppresses an intermediate approval trajectory; missing authority introduces an interruption and continuation without changing the successful final effect.

## IR and transformation reuse

Runtime 2 maps its native state to the existing Stage-9 `AUTHORIZATION` frontend:

| Native event/state | Existing IR concept |
|---|---|
| Stored approval lookup | `AUTHORIZE` |
| Unresolved `ToolApprovalItem` | `REQUEST_LOCAL_CONSENT` |
| `RunState.approve` | `PERSIST_AUTHORIZATION` |
| Resumed approval status check | `VERIFY_AUTHORIZATION` |
| Synthetic tool callback | `COMMIT_EFFECT` |

The common core is unchanged:

- `stage9_adaptive.ir.build_program("AUTHORIZATION")`
- the same private/public annotations;
- `stage9_adaptive.runtime.AdaptiveNormalizer`;
- public horizon `H=5`;
- three ORAM access slots per round;
- fixed final commit slot and no dummy external effects.

Only the runtime boundary adapter is framework-specific. No hand-written Runtime-2 B2 trajectory was added.

## External-validity judgment

Two independently maintained public runtimes now exhibit the same high-level phenomenon under their existing security semantics. This materially strengthens external validity, although it does not establish prevalence across all agent frameworks or all approval designs.

