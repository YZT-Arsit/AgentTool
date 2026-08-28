# Live M3 runtime audit

## Provenance and unchanged semantics

- Microsoft Agent Framework: native `ToolApprovalMiddleware`, commit `af461de51da16f5cb800ff7febc0f8f96355607a`.
- OpenAI Agents SDK: native HITL interruption/`RunState.approve`/resume path, commit `a40ae9803e6b7a79faa246293f56adb100d5868b`.

Instrumentation adds a local deterministic model/client, a proposal-only mock tool, trace hooks, ORAM-backed mediator slots, framing, cadence, and a trusted commit gate. It does not add an approval or retry branch. Native tools prepare a proposal; only the public commit slot can create the synthetic external effect.

## Live enforcement

`live_core.py` executes native calls inside slots, materializes actual binary frames, and waits on `perf_counter` deadlines. It does not rewrite recorded timestamps. A short high-resolution boundary spin is needed on Windows after coarse sleep. M3 uses five rounds, three Path-ORAM accesses per round, a public approval epoch, and fixed-size messages. P99 cadence is selected from 64 pooled training episodes spanning both families, without class-conditional selection.

Agent Framework used Delta=2.929 ms; the OpenAI SDK used Delta=7.788 ms. Both used 16,384-byte fixed mediation frames. One- and two-second approval-window checks resumed at the public boundary and retained one real effect. No fake user prompt was generated.

## Outcome

Structural equality: pass. Actual serialized-size equality: pass. Effect/authorization semantics: pass. Timing privacy: fail. Aggregate M3 timing AUC was 0.588 and combined AUC 0.598, versus 0.5 chance. The implementation therefore cannot support the full structural-and-temporal claim.

