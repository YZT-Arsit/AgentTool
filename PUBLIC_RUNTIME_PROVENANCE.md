# Public Runtime Provenance

## L2 decision

```text
L2 ACHIEVED
```

Stage 9 exercised the independently existing tool-approval execution path in [Microsoft Agent Framework](https://github.com/microsoft/agent-framework). The framework documents `ToolApprovalMiddleware` as coordinating session-backed standing rules, queued requests, collected responses, and approval prompts. The measured private state was whether a matching standing approval rule already existed in `AgentSession` state.

## Frozen source

| Field | Value |
|---|---|
| Repository | `https://github.com/microsoft/agent-framework.git` |
| Commit | `af461de51da16f5cb800ff7febc0f8f96355607a` |
| Retrieved | 2026-08-26 |
| License | MIT |
| Local clone | `external_stage9/agent-framework/` |
| Source status after probe | clean (`git status --short` empty) |
| Semantic patches | none |
| Instrumentation patches | none in upstream source |

Files exercised by the Python approval path:

| File | SHA-256 |
|---|---|
| `agent_framework/_harness/_tool_approval.py` | `CE9B85F6F9B7ECA9EFDBD916FCE06829030944427CE5C1F2427D0569B08483AA` |
| `agent_framework/_tools.py` | `AA52744502388B1D5E734E7E5849AF152BC1BF24B352041FEEF2D8BE33731BC8` |
| `agent_framework/_agents.py` | `362F9CC98FDA41CEFC7A900FA7E5900B61F21783F69349A482F8EF26F6A69BEC` |
| `agent_framework/_sessions.py` | `F5954F9651B2089B82886E506AADC4414A3690D78A803B4FA5EBBA8F0E3C3CE6` |

The official repository's standing-rule unit test was run locally and passed:

```text
test_tool_approval_middleware_always_approve_tool_rule: PASS
```

## Project-added harness

[`stage9_adaptive/public_runtime_probe.py`](stage9_adaptive/public_runtime_probe.py) adds only:

- a deterministic response-queue client that makes no model/network calls;
- a synthetic local tool;
- boundary trace collection after each `Agent.run` call;
- fixed synthetic arguments and result serialization.

It does not modify approval matching, persistence, request generation, resume, function invocation, or session-state semantics. These remain upstream code. No real user, account, credential, API, or external tool was used.

## Measured L2 path

The standing-rule branch was prepared by completing an ordinary prior approval with the framework's existing `create_always_approve_tool_response`. Preparation was outside the measured trace. The measured task and final effect were identical in both states.

| Private state before measured task | Application invocations | Client calls | Result | Effects |
|---|---:|---:|---|---:|
| standing rule exists | 1 | 2 in one middleware invocation | function result + final text | 1 |
| standing rule absent | 2 | 1 + 1 | approval request, then function result + final text | 1 |

The exact boundary trace is in [`results_stage9/public_runtime_probe.json`](results_stage9/public_runtime_probe.json).

This is evidence of natural adaptive trajectory variation. It is not a claim that Microsoft Agent Framework attempts trajectory-oblivious privacy.

## Search record

Official/current candidates considered on 2026-08-26:

| Candidate | Public source checked | Head observed | Disposition |
|---|---|---|---|
| Microsoft Agent Framework | `microsoft/agent-framework` | `af461de…` | integrated; qualifying standing-approval path |
| CaMeL | `google-research/camel-prompt-injection` | `f083b6b…` | official artifact found; requires configured model API for main workflow and was not needed after qualifying local L2 path was found |
| Fides | `microsoft/fides` | `669c046…` | public IFC tutorial/runtime material; no qualifying independently existing persistent consent/retry path selected |
| Fides Gateway | `microsoft/fides-gateway` | `3f39af1…` | public IFC MCP gateway; no qualifying standing-consent path selected |
| PAuth | paper and author/repository search | no official implementation located in targeted search | not integrated |
| PACT | paper and author/repository search | no official implementation located in targeted search | not integrated |
| SecureClaw | multiple repositories with that name | ambiguous/non-matching candidates | not treated as the research-system implementation |

The CaMeL repository describes itself as a research artifact and warns that the interpreter may contain bugs; it was not reclassified as L2 for this question merely because code exists. The targeted search is not an exhaustive literature review.
