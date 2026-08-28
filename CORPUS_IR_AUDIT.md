# Corpus IR Audit

## Phase-3 result

The static corpus audit is complete over every Python file in the locally
available pinned example/test-example roots. It does **not** support the prior
95.3% generality impression. On the conservative behavior-instance denominator,
current IR coverage is **3,574 / 7,386 = 48.39%**. The remaining 3,812 instances
are explicitly `UNSUPPORTED`.

| Framework | Pinned commit | Files | Agent constructor instances | Workflow instances | Behavior instances | Compiled | Shared primitive | Unsupported | Coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OpenAI Agents SDK | `a40ae9803e6b7a79faa246293f56adb100d5868b` | 216 | 147 | 0 | 1,904 | 310 | 406 | 1,188 | 37.61% |
| Microsoft Agent Framework | `af461de51da16f5cb800ff7febc0f8f96355607a` | 98 | 429 | 328 | 5,482 | 1,398 | 1,460 | 2,624 | 52.13% |
| **Combined** | — | **314** | **576** | **328** | **7,386** | **1,708** | **1,866** | **3,812** | **48.39%** |

All 314 files parsed successfully. The Microsoft checkout is sparse: the local
roots are `python/tests/samples` (5 files) and
`python/packages/core/tests` (93 files); the separately referenced upstream
`python/samples` tree is not present locally. No network fetch was attempted.

## What was counted

The extractor is import-free and AST based. `CORPUS_MANIFEST.csv` contains one
row per file and reports constructors/workflows/tools/handoffs/conditions/loops,
fan-out/fan-in, agents-as-tools, dynamic instructions, guardrails,
state/memory, HITL/resume, middleware, MCP, and nested patterns.
`CORPUS_BEHAVIOR_INSTANCES.csv` contains the auditable source path, line,
behavior kind, classification, and reason for every denominator instance.

These are **constructor instances, not unique independently authored Agents**.
Tests often construct the same class repeatedly. The measured count 576 must
not be advertised as “576 Agents.” Likewise, generated registry rows are not
part of this corpus.

## Classification policy

- Static instructions, termination, logical static handoffs, workflows, and
  sequential edges are `COMPILED`.
- LLM, Tool, and MCP work are `SHARED_PRIMITIVE`; this classification says only
  that heavy execution can sit behind the common boundary, not that remote
  endpoint or provider privacy follows.
- Arbitrary Python conditions/loops, dynamic instruction callbacks, guardrails,
  framework persistence/session objects, HITL/resume, middleware, native
  fan-out/fan-in, and nested Agent-as-Tool execution remain `UNSUPPORTED`.

No opcode was added merely to improve coverage. In particular, existing
`BRANCH`, `STATE_GET`, and `STATE_SET` opcodes do not make arbitrary Python
predicates or framework persistence implementations declarative.

## Largest unsupported classes

| Behavior | Unsupported instances | Reason |
| --- | ---: | --- |
| State/memory integration | 1,589 | Native persistence/session semantics are not automatically lowerable |
| Middleware | 932 | Arbitrary runtime middleware remains native code |
| Conditional edge | 738 | Arbitrary Python predicates are not declarative branch expressions |
| Loop | 165 | No proven public-bounded loop lowering in the current IR |
| Fan-out/fan-in | 156 | Parallel scheduling is absent from the one-transition executor |
| HITL/resume | 143 | Exact interruption, persistence, and resume semantics are not implemented |
| Agent-as-Tool | 61 | Nested Agent execution has no exact current IR transition |

## Precision boundary

This is a conservative syntactic audit, not a semantic parser for either
framework. Control-containing `if`/loop and state/middleware patterns may include
test harness scaffolding; treating ambiguous instances as unsupported lowers,
rather than inflates, coverage. The raw rows permit a future manual precision
sample. Dynamic native-vs-compiled execution in Phase 4 is the fidelity test and
may not reinterpret this static percentage.

## Phase-3 gate

PASS as an audit; **current Agent-IR generality is limited**. The corpus outputs
were generated from pinned local source with no external execution. Phase 4 may
evaluate only supported, source-traceable behavior strata and must keep missing
unsupported strata visible.

