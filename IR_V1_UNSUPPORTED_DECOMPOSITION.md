# IR-v1 unsupported-behavior Pareto decomposition

## Scope and interpretation

This audit decomposes all **3,812** rows that IR-v1 recorded as `UNSUPPORTED`. It never changes that disposition. The instance-level classification is a second, non-coverage annotation answering what kind of semantics the source appears to contain:

- `STRUCTURED_BOUNDED_CANDIDATE`: source-local syntax exposes a finite/declarative shape that may be a candidate for exact lowering;
- `ARBITRARY_CALLBACK_OR_RUNTIME`: source invokes general Python/framework/runtime computation;
- `MIXED_OR_BOUND_NOT_PROVEN`: a structured API is visible, but its bound or exact semantics are not established;
- `EXTRACTOR_FALSE_POSITIVE_OR_OUT_OF_SCOPE`: the frozen lexical extractor recorded a row that is not the claimed Agent-control family.

These labels are conservative source classifications—not successful compilation results and not hypothetical coverage estimates. The complete 3,812-row evidence is in `IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv`; representative source-traceable examples are in `IR_V1_UNSUPPORTED_EXAMPLES.csv`.

## Pareto table

| Rank | Family | Instances | Share | Files | OpenAI inst/files | Microsoft inst/files | Structured | Arbitrary | Mixed | Extractor artifact |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | state_memory | 1,589 | 41.68% | 101 | 325 / 56 | 1,264 / 45 | 0 | 0 | 1,589 | 0 |
| 2 | middleware | 932 | 24.45% | 14 | 0 / 0 | 932 / 14 | 0 | 932 | 0 | 0 |
| 3 | conditional_edge | 738 | 19.36% | 195 | 530 / 160 | 208 / 35 | 450 | 142 | 0 | 146 |
| 4 | loop | 165 | 4.33% | 75 | 101 / 50 | 64 / 25 | 6 | 0 | 159 | 0 |
| 5 | fanout_fanin | 156 | 4.09% | 64 | 82 / 41 | 74 / 23 | 0 | 2 | 2 | 152 |
| 6 | hitl_resume | 143 | 3.75% | 39 | 97 / 30 | 46 / 9 | 63 | 0 | 80 | 0 |
| 7 | agents_as_tools | 61 | 1.60% | 12 | 25 / 9 | 36 / 3 | 0 | 0 | 61 | 0 |
| 8 | dynamic_instructions | 18 | 0.47% | 16 | 18 / 16 | 0 / 0 | 0 | 5 | 13 | 0 |
| 9 | guardrail | 7 | 0.18% | 3 | 7 / 3 | 0 / 0 | 0 | 7 | 0 | 0 |
| 10 | conditional_handoff_callback | 3 | 0.08% | 3 | 3 / 3 | 0 / 0 | 0 | 3 | 0 | 0 |
| **Total** | — | **3,812** | **100%** | — | **1,188 / —** | **2,624 / —** | **519** | **1,091** | **1,904** | **298** |

The three largest families account for 85.49% of unsupported instances. This concentration must not be read as an easy coverage gain: state/memory is mostly semantically unresolved, middleware is general runtime code, and conditional edges combine a restricted declarative subset with arbitrary predicates and detector artifacts.

## Exact-lowering feasibility by family

| Family | Exact semantics-preserving lowering | Primitive required | Boundary |
| --- | --- | --- | --- |
| state_memory | Partial subset | Typed `STATE_GET/SET/APPEND/CAS`, session/version/transaction/failure semantics | Recognizable APIs do not establish exact framework persistence or object behavior. |
| middleware | No general lowering | Restricted stage-specific hooks, otherwise a trusted native boundary | Middleware may intercept, mutate, retry, persist, or perform arbitrary I/O. |
| conditional_edge | Partial subset | Typed side-effect-free predicate bytecode and `BRANCH` | Literal/comparison predicates appear feasible; arbitrary calls and Python truth semantics do not. |
| loop | Partial subset | Public-bounded `LOOP`, explicit counter and break/continue/failure semantics | Only six rows had a source-local literal finite bound; the rest were unproven. |
| fanout_fanin | Partial subset | `FORK/JOIN/PARALLEL_GROUP`, public maximum width/order/cancellation/reducer | 152/156 rows were lexical overmatches such as ordinary `join`; two were general runtime concurrency; two exposed real graph APIs without a proven static bound. |
| hitl_resume | Partial subset | `HITL_WAIT/HITL_RESUME`, durable continuation, approval token, rejection/cancellation | 63 rows expose explicit approval/resume syntax; 80 still have unresolved policy or continuation semantics. |
| agents_as_tools | Partial subset | `AGENT_AS_TOOL_CALL/RETURN`, bounded capsule stack, protected argument/result ABI | Exactness depends on independently compiling and bounding the nested Agent. |
| dynamic_instructions | No general lowering | Bounded templates and typed context selectors for a subset; otherwise trusted native callback | Five rows construct instructions via calls; 13 referenced values that the frozen extractor did not resolve. |
| guardrail | No general lowering | Restricted declarative policy predicates, otherwise trusted native guardrail | The observed guardrails are callable application code. |
| conditional_handoff_callback | No general lowering | Restricted declarative handoff-filter predicate, otherwise trusted native callback | All three rows attach native callback/filter semantics. |

## Representative traceable examples

- `state_memory`: OpenAI `examples/agent_patterns/agents_as_tools_conditional.py:131`, `state = result.to_state()`—structured surface, exact continuation-state semantics unresolved.
- `middleware`: Microsoft `python/packages/core/tests/core/test_agent_hooks.py:168`, `create_agent_hooks_middleware([AllowGuard()])`—general middleware execution.
- `conditional_edge`: OpenAI `examples/agent_patterns/agents_as_tools_conditional.py:135`, `if confirmed:` is a structured candidate; line 143, `if is_auto_mode():` invokes arbitrary computation; `examples/agent_patterns/agents_as_tools.py:82` is only a module-entry guard recorded by the frozen detector.
- `loop`: OpenAI `examples/sandbox/extensions/daytona/usaspending_text2sql/setup_db.py:220`, `for attempt in range(120):` has a literal bound; `examples/agent_patterns/agents_as_tools_conditional.py:126`, `while result.interruptions:` does not.
- `fanout_fanin`: Microsoft `python/packages/core/tests/workflow/test_workflow.py:224` uses `add_fan_out_edges`; OpenAI `examples/agent_patterns/agents_as_tools_conditional.py:109` is ordinary `str.join`, demonstrating detector overbreadth.
- `hitl_resume`: OpenAI `examples/agent_patterns/agents_as_tools_conditional.py:30`, `@tool(needs_approval=True)`, exposes structured approval configuration; line 67 combines approval with unresolved nested Agent-as-Tool semantics.
- `agents_as_tools`: OpenAI `examples/agent_patterns/agents_as_tools.py:38`, `spanish_agent.as_tool(`—recognizable wrapper with unresolved nested execution semantics.
- `dynamic_instructions`: OpenAI `examples/basic/dynamic_system_prompt.py:28`, `instructions=custom_instructions`—the frozen extractor did not resolve whether the reference is data or executable callback.
- `guardrail`: OpenAI `examples/agent_patterns/input_guardrails.py:46`, `async def math_guardrail(`—arbitrary callback body.
- `conditional_handoff_callback`: OpenAI `examples/handoffs/message_filter.py:69`, `handoff(... input_filter=spanish_handoff_message_filter)`—native filter callback.

All paths are relative to the corresponding pinned checkout. The CSV example artifact includes commit, path, line, excerpt, and classification for independent verification.

## Falsification findings

1. IR-v1's 48.39% cannot be interpreted as a clean fraction of unique semantic capabilities: the unsupported denominator includes 298 extractor false positives/out-of-scope lexical matches.
2. Removing those rows after the fact would reinterpret the frozen result, so they remain unsupported in IR-v1 and are only annotated separately.
3. The largest genuine families are not solved by adding opcode names alone. State/memory requires an exact persistence model, and middleware/guardrails/callbacks require either a restricted language or an explicit native boundary.
4. This audit makes no estimate of IR-v2 coverage. Only an implemented IR-v2 compiler and dynamic equivalence evaluation on the identical frozen corpus may produce a new coverage number.
