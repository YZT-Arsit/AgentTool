# Semantic Preservation Report

## Phase-4 result

Seventy-two native framework executions were compared with the current compiled
IR using exact semantic projections and deterministic local model/Tool results.
No external model or provider was used.

```text
Execution fidelity = 54 / 72 = 75.0%
```

| Stratum | Framework | Source-traceable pattern | Executions | Exact matches | Fidelity |
| --- | --- | --- | ---: | ---: | ---: |
| Simple Agent | OpenAI Agents SDK | `examples/basic/hello_world.py` | 18 | 18 | 100% |
| Tool call | OpenAI Agents SDK | `examples/basic/tools.py` | 18 | 0 | 0% |
| Logical handoff | OpenAI Agents SDK | `examples/handoffs/message_filter.py` | 18 | 18 | 100% |
| Simple Agent | Microsoft Agent Framework | `python/packages/core/tests/core/test_agents.py` | 18 | 18 | 100% |

The 72 rows are repeated deterministic executions across four strata, not 72
independently authored Agent programs. They meet the requested execution-count
target but provide narrower semantic diversity than that raw count suggests.

## Exact projection

Every comparison includes selected Tool, canonicalized Tool arguments, handoff
target, private state-transition sequence, external effect sequence/count,
termination class, sanitized final result, and model-call count. Textual
similarity is not used.

Native executions use the pinned runtime objects and runners:

- OpenAI `Agent`, `Runner`, `function_tool`, handoff machinery, and
  `agents.testing.ScriptedModel`;
- Microsoft `Agent.run` with a local deterministic client implementing the
  pinned test protocol.

The compiled side uses `compile_workload`, fixed `AgentCapsule` rows, and the
same deterministic primitive outputs.

## Falsification finding

All 18 ordinary Tool-call cases fail in the same substantive way. Native SDK
semantics are:

```text
LLM -> TOOL(arguments) -> LLM -> RETURN
```

The current compiler emits:

```text
LLM -> TOOL -> RETURN(DONE event)
```

After `TOOL_RESULT`, no row matches. The compiled execution stalls, loses Tool
arguments/effect projection, omits the second model call, and cannot produce the
sanitized final result. `SEMANTIC_FAILURE_CASES.csv` preserves all 18 failures.

This is not patched by adding an ad hoc state transition: arbitrary agents may
call zero, one, or several Tools before returning to the model. A sound bounded
Tool/model loop and an explicit protected argument/result ABI are required.
Until those semantics are implemented and retested, the Tool behavior cannot be
claimed `SHARED_PRIMITIVE` end to end merely because provider execution can sit
behind the Gateway.

## Missing strata

The current IR does not support exact dynamic evaluation for Agent-as-Tool,
arbitrary conditional routing, bounded loop, fan-out/fan-in, framework state
and session persistence, HITL/resume, dynamic callbacks, or nested Agent
patterns. These omissions remain visible in `CORPUS_IR_COVERAGE.csv`; they were
not replaced with hand-written success traces.

## Phase-4 gate

Completed, with a negative result. Exact fidelity is **75.0% on the evaluated
subset**, corpus coverage is only **48.39%**, and the canonical compiler is not
semantics-complete for ordinary Tool loops. Phase 5 may exercise only the
working simple/handoff path as validated behavior; Tool-heavy workflows must be
reported as failed or blocked, not silently repaired per task.

