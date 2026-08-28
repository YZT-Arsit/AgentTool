# Pareto decomposition of the frozen 1,904 MIXED/UNPROVEN instances

## Non-negotiable interpretation

The 1,904 rows are unchanged members of the frozen IR-v1 unsupported set.
Classification below is source triage, not support, implementation, or a
hypothetical coverage estimate. Every machine-readable row therefore records
`implemented_and_semantically_tested=NO` and `coverage_gain_claimed=NO`.

| Family | Instances | Source files | OpenAI | Microsoft | Source-bounded | Contract-bounded | Dynamic | Extractor-ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| State / memory | 1,589 | 101 | 325 | 1,264 | 0 | 72 | 212 | 1,305 |
| Loop | 159 | 73 | 99 | 60 | 10 | 0 | 35 | 114 |
| HITL / resume | 80 | 32 | 41 | 39 | 0 | 69 | 0 | 11 |
| Agent-as-Tool | 61 | 12 | 25 | 36 | 55 | 6 | 0 | 0 |
| Dynamic instructions | 13 | 13 | 13 | 0 | 0 | 0 | 13 | 0 |
| Fan-out / fan-in | 2 | 1 | 0 | 2 | 0 | 2 | 0 | 0 |
| **Total** | **1,904** | — | **503** | **1,401** | **65** | **149** | **260** | **1,430** |

Source-file counts are per family and therefore do not sum: one file may contain
multiple families.

## Feasibility, required primitive, and examples

| Family | Exact lowering outlook | Required primitive | Representative pinned source evidence |
| --- | --- | --- | --- |
| Agent-as-Tool | Feasible for static targets with bounded recursion/call depth; callback-bearing forms require a declared contract. | Private `CALL_AGENT`/`RETURN_AGENT` stack and public depth bound. | OpenAI `examples/agent_patterns/agents_as_tools.py:38`; Microsoft `python/packages/core/tests/core/test_agent_hooks.py:2235`. |
| HITL/resume | Feasible only for explicit framework interruption records and a bounded public resume policy. | `SUSPEND`, private continuation token, `RESUME`, public horizon. | OpenAI `examples/agent_patterns/human_in_the_loop_custom_rejection.py:88`. |
| Fan-out/fan-in | The two instances are framework-structured, but exact width/order/result semantics must be tested. | Bounded `FORK`/`JOIN` with deterministic result ordering. | Microsoft `python/packages/core/tests/workflow/test_workflow.py:224`. |
| Loop | Ten literal/range cases are source-bounded; 35 runtime/async termination cases are genuinely dynamic; 114 remain extractor-ambiguous. | Public loop bound plus `LOOP_HEAD`/`LOOP_NEXT`; dynamic cases need an explicit overflow policy. | OpenAI `examples/agent_patterns/agents_as_tools_conditional.py:126` (`while result.interruptions`). |
| Dynamic instructions | Not exactly lowerable as fixed control without executing the callback or restricting its language. | Declared bounded instruction function or shared callback primitive; arbitrary Python remains unsupported. | OpenAI `examples/basic/dynamic_system_prompt.py:28`. |
| State/memory | Framework contract cases may be feasible for explicit scoped key/value APIs; external stores and arbitrary lifecycle hooks are not automatically lowerable. Most rows remain ambiguous because broad name heuristics do not establish semantics. | Typed scoped `STATE_GET/SET/EXISTS`, transaction/lifecycle contract, explicit backend boundary. | OpenAI `examples/memory/advanced_sqlite_session_example.py:35`; `examples/agent_patterns/agents_as_tools_conditional.py:131`. |

The exact row-level decision, source excerpt, and classification basis are in
`MIXED_UNPROVEN_DECOMPOSITION_V2.csv`. The preserved preliminary pass is kept as
`MIXED_UNPROVEN_DECOMPOSITION_V2_PRELIMINARY.csv`; it is not citable because its
AST selector sometimes classified a child identifier rather than the enclosing
source construct.
