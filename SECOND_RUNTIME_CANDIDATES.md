# Second Runtime Candidate Audit

Audit date: 2026-08-26. The strict `Qualifies L2?` column means that all Stage-10 conditions were verified from public code and a local execution; a documented but unexecuted feature is marked NO rather than inferred to qualify.

| Runtime | Relevant feature | Adaptive mediation? | Same final effect possible? | Public code? | Qualifies L2? |
|---|---|---:|---:|---:|---:|
| OpenAI Agents SDK (Python) | Native `needs_approval`, `RunResult.interruptions`, stored approval decisions, serialized `RunState`, resume | YES | YES | YES | **YES — selected** |
| Microsoft Agent Framework | Standing approval rules and approval middleware | YES | YES | YES | NO — already Runtime 1, so not independent evidence |
| LangChain/LangGraph | HITL middleware, checkpointed interrupt and `Command(resume=...)` | YES | YES after approval | YES | NO — current docs establish policy-triggered pause/resume, but not a native standing private approval that skips the same pending call; not executed |
| PydanticAI | Deferred tools, `ApprovalRequired`, approval results, follow-up run | YES | YES after approval | YES | NO — plausible additional candidate, but prior-decision skip semantics were not independently executed under the strict gate |
| Google ADK | `FunctionTool(require_confirmation=True)` and resumable confirmation state | YES | YES after confirmation | YES | NO — native confirmation exists, but a standing prior-state bypass was not independently established and executed |
| Semantic Kernel / current Microsoft Agent Framework workflows | `ApprovalRequiredAIFunction`, `RequestInfoEvent`, workflow resume | YES | YES after approval | YES | NO — current documented implementation is in the Microsoft successor/runtime family already used as Runtime 1 |
| Microsoft AutoGen | `UserProxyAgent` human feedback; tool-approval proposals remain open issues | PARTIAL | PARTIAL | YES | NO — no standardized native tool-approval interception path was established in the inspected code/docs |
| CrewAI | Task-level human input and external HITL integrations | PARTIAL | PARTIAL | YES | NO — no qualifying native private approval-state skip/resume path was verified |

## Selection rationale

The [OpenAI Agents SDK HITL guide](https://github.com/openai/openai-agents-python/blob/main/docs/human_in_the_loop.md) documents the exact native distinction needed here: an existing decision in `RunContextWrapper` proceeds without prompting; an absent decision emits an interruption; the caller records a decision in `RunState` and resumes. Sticky decisions also survive serialization. That behavior is implemented before this project and ran with the SDK's provider-neutral `ScriptedModel`, so neither an API nor a semantic patch was needed.

The runner-up candidates are real HITL systems, not negative evidence against the claim. They were rejected only because Stage 10 required independently executed proof of the exact state-dependent same-effect pair, and OpenAI Agents SDK already satisfied that gate cleanly.

## Rejection evidence

- [LangChain/LangGraph HITL middleware](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/human-in-the-loop.mdx) pauses matching tool calls and resumes a checkpoint after a supplied decision. The inspected documentation does not claim that a private standing approval suppresses a future matching interruption.
- [PydanticAI deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/) support approval-required calls and separate follow-up runs, but Stage 10 did not execute a prior-state bypass pair.
- [Google ADK confirmations](https://adk.dev/tools-custom/confirmation/) provide native confirmation and pause/resume, but the strict prior-decision comparison was not verified.
- AutoGen's public issues [#4894](https://github.com/microsoft/autogen/issues/4894), [#5891](https://github.com/microsoft/autogen/issues/5891), and [#7405](https://github.com/microsoft/autogen/issues/7405) describe missing/proposed standardized approval interception; `UserProxyAgent` feedback alone is not the required native security-mediation state.

