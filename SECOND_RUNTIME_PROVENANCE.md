# Second Runtime Provenance

## Frozen source

| Field | Value |
|---|---|
| Runtime | OpenAI Agents SDK for Python |
| Repository | `openai/openai-agents-python` |
| Repository URL | https://github.com/openai/openai-agents-python |
| Local checkout | `external_stage10/openai-agents-python/` |
| Commit | `a40ae9803e6b7a79faa246293f56adb100d5868b` |
| Commit timestamp | `2026-08-26T14:22:24+09:00` |
| Package version at commit | `0.22.0` |
| License | MIT |
| Upstream working tree | Clean after instrumentation and experiment |
| Network/API use during run | None; provider-neutral `agents.testing.ScriptedModel` only |

The native component is the SDK's human-in-the-loop function-tool approval flow: `FunctionTool.needs_approval`, `RunContextWrapper` approval records, `ToolApprovalItem`, `RunState.approve`, `RunResult.interruptions`, and `Runner.run` resume.

## Relevant upstream files

| File | Role | SHA-256 |
|---|---|---|
| `src/agents/run_context.py` | Stores and resolves per-call/sticky approval decisions | `8dbb92be4d531ce88e92cc16c3c7c7bd1d8a508cd91b9f758ffe6bf83d85979a` |
| `src/agents/run_state.py` | Public approve/reject and durable resume state | `caa97702297a28a814d0f19087d4721c751710b189105f92e89b09b6adcd155c` |
| `src/agents/run_internal/tool_planning.py` | Selects approved runs or emits pending interruptions | `a67b75358f962a158fce26ede0245b8196c9c84f1f7a8da8152c906e1c2ed75b` |
| `src/agents/run_internal/tool_execution.py` | Checks stored status before invoking the approval predicate/tool | `08cef92463e120de97944e1d0320ddd7c041513ace5add5d6d0bc059cb6ec20a` |
| `src/agents/run.py` | Public runner/resume entry point | `c84285164ec9ace11a80aad09f6bf4c10e9ba9113fdbdf91d826f1c259c59e82` |
| `docs/human_in_the_loop.md` | Native HITL contract and examples | `83318371e747bcec5ff6e07c8c905fa9a5c7936888c89707aae77ffc20e2bbf5` |
| `LICENSE` | MIT license text | `13df7812ca53ecaae1cb4a868844bb598373047ae1d580e4debfbef1dd5b6915` |

Official documentation: [Human in the loop](https://openai.github.io/openai-agents-python/human_in_the_loop/) and its [repository source](https://github.com/openai/openai-agents-python/blob/main/docs/human_in_the_loop.md).

## Unmodified runtime logic

The following behavior is upstream:

1. A function tool declares `needs_approval=True`.
2. The runner checks `RunContextWrapper.get_approval_status`.
3. A resolved approval selects the tool for execution without another approval prompt.
4. An unresolved call becomes a `ToolApprovalItem` interruption and the run pauses.
5. `RunState.approve` records the decision.
6. A subsequent `Runner.run(agent, state)` resumes and executes the approved call.
7. An unresolved resumed state remains pending rather than executing the effect.

No file under `external_stage10/openai-agents-python/` was modified. Four relevant upstream tests passed locally:

```text
tests/test_hitl_error_scenarios.py::test_resumed_hitl_executes_approved_tools
tests/test_hitl_error_scenarios.py::test_resume_honors_permanent_namespaced_function_approval_with_new_call_id
tests/test_hitl_error_scenarios.py::test_resume_skips_needs_approval_checker_when_status_resolved

4 passed
```

The first upstream test is parameterized, hence four total cases.

## Experiment instrumentation

Project-owned code is limited to:

- a deterministic `ScriptedModel` response containing one synthetic `send_message` call and one final text response;
- a local synthetic tool callback that appends one in-memory effect record;
- synthetic state initialization using the public `RunState.approve` API;
- boundary logging for runner invocation, interruption, local approval decision, public effect commit, and sanitized result;
- a frontend mapping of the native approval state to the unchanged Stage-9 `AUTHORIZATION` IR;
- B1 per-invocation ORAM trace shaping and B2 invocation of the unchanged Stage-9 bounded normalizer.

The instrumentation adds no approval rule, retry branch, consent rule, authorization rule, or hidden-label control flow. Ground truth is serialized separately from each `host_visible_trace`.

## Measurement boundary

Both branches first execute the identical public task until the same pending native tool call exists. That common prelude is outside the measured continuation. The measured private state is whether that exact call already has a native SDK approval decision in `RunState`.

- Approval present: one measured `Runner.run` continuation, then effect.
- Approval absent: one measured continuation returns the native interruption; the synthetic local reviewer approves; a second `Runner.run` resumes; then the same effect occurs.

This boundary isolates existing-versus-missing private mediation state without creating the SDK's branch.

The SDK can serialize `RunState`, but this experiment keeps that state inside the trusted mediator. Raw serialized-state bytes and contents are therefore not part of the host structural view; exposing them would introduce a separate application-state content channel. The trace records runner/message boundary event counts instead. The native local run performs no host-visible persistent-storage access. B1/B2 add only the existing project ORAM abstraction for the protected mediation-state schedule.
