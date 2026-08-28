# IR-v2 support definition

## Two independent metrics

`STATIC_LOWERING_COVERAGE` and `EXECUTABLE_SEMANTIC_SUPPORT` are not interchangeable.

### Static lowering coverage

A source behavior is statically lowered when the versioned compiler maps it to a defined IR construct without classifying it as a shared opaque callback or unsupported native behavior. Static recognition alone says nothing about whether the runtime can execute the behavior faithfully.

The immutable IR-v1 value remains `3574/7386 = 48.39%` under its historical compiled-plus-shared definition. IR-v2 must use new labels and new output files on the same 314-file corpus; it may not rewrite that value.

### Executable semantic support

A behavior is executable-supported only when all five gates pass:

1. a source-traceable framework behavior is lowered by the IR-v2 compiler;
2. the trusted interpreter executes the lowered behavior;
3. required private arguments, results, control state, and errors are represented rather than discarded into an opaque label;
4. a native-vs-compiled test executes that behavior from the pinned framework source stratum;
5. the exact structured semantic projection matches.

The projection includes, where relevant: Tool identity, arguments, call ID, result, next-model context, handoff target, branch choice, state updates, effect sequence/count, termination class, sanitized final output, and model-call count. Text similarity is not a substitute for equality of these fields.

## Current measured scopes

- Development regression support: **72/72 executions**, including **18/18 Tool
  workflows**. These cases guided the Tool-loop repair and are not an untouched
  semantic holdout.
- Untouched holdout attempt: **8 valid passes, 12 harness-invalid cases** out of
  20. The invalid cases were preserved and not rerun; therefore no holdout
  fidelity percentage is claimed.
- Fully passing tested support units: **11/11** in `IR_V2_EXECUTABLE_SUPPORT.csv`. The added
  unit is the bounded `SESSION_PRIVATE`/`AGENT_PRIVATE`/`CALL_LOCAL`
  GET/SET/EXISTS store, checked against the source-traceable Microsoft
  `AgentSession.state` dictionary subset. It does not promote arbitrary session,
  checkpoint, memory, database, or callback instances in the static corpus.
- `Agent.as_tool()` now has explicit private `CALL_AGENT`/`RETURN_AGENT`
  development implementations for actual OpenAI and Microsoft native objects.
  The focused development tests pass, but the untouched Agent-as-Tool holdout
  cases were harness-invalid. It therefore remains outside confirmed holdout
  support and does not alter static coverage.
- Corpus-wide executable support: **not inferred** from the 72 executions. A behavior instance without a source-traceable dynamic equivalence test does not become executable-supported merely because it resembles a passing unit.
- IR-v2 core static corpus coverage: **3,574/7,386 = 48.39%** on the
  exact frozen 314-file membership. `IR_V2_STATIC_CORPUS_COVERAGE.csv` records
  1,708 lowered control instances, 1,866 represented shared-heavy invocations,
  and all 3,812 historical unsupported instances unchanged. This equality with
  IR-v1 is expected: the core repair fixes executable Tool semantics but adds no
  newly accepted corpus behavior family.

## Core bounded semantics

IR-v2 currently represents:

```text
MODEL
  -> FINAL -> RETURN
  -> TOOL_CALL(name, arguments, call_id)
       -> TOOL_RESULT(call_id, result)
       -> private context reinsertion
       -> MODEL_RESUME
       -> ... bounded repetition ...
       -> FINAL -> RETURN
  -> HANDOFF(target, call_id)
       -> private logical Agent transition
       -> MODEL_RESUME
```

Tool and model failures, unknown Tools, unresolved handoffs, and bound exhaustion are explicit private runtime states. Tool operation IDs are idempotent in the interpreter: repeating a call ID returns the prior result and does not repeat an effect.

## Non-claims

This core result does not claim corpus-wide support for state/session systems,
arbitrary Python predicates, Agent-as-Tool, HITL, fork/join, middleware,
arbitrary callbacks, live Gateway timing, or resource privacy. Agent-as-Tool is
an explicitly partial bounded implementation, not a corpus-wide claim.
