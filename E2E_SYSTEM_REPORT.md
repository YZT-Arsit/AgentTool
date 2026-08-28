# End-to-End System Report

## Phase-5 decision

No complete canonical end-to-end workflow was executed on this host. The status
is **NOT_COMPLETED_ENVIRONMENT**, compounded by a genuine compiler failure for
ordinary Tool workflows. This report does not infer success from independently
passing components.

## What connects in executed evidence

The official SimplePIR bridge completed one real and two dummy scheduled
queries; the recovered 1,024-byte capsule was installed directly into the
trusted Control Kernel and enabled its first LLM transition. This establishes:

```text
real SimplePIR -> recovered capsule -> trusted Control Kernel transition
```

It does not establish the remainder of the system.

## Live execution blocker

Worker and local provider processes launched, but Windows Application Control
refused the newly built `gateway-pacer.exe` with WinError 4551. Directly
invoking that local binary produced the same policy error. No policy bypass,
renaming workaround, alternate executable loader, or external host was used.
Therefore these links remain unexecuted:

```text
Control Kernel -> opaque U -> Gateway Pacer/Worker -> local provider
               -> fixed response -> Control Kernel result consumer
```

The implementation exists and unit tests validate its interfaces, but code
existence is not an integration result.

## Semantic blocker

The native-vs-compiled audit independently falsified the ordinary
`LLM -> TOOL -> LLM` family. The current compiler loses exact arguments/effects,
omits the second LLM transition, and stalls on `TOOL_RESULT`. Consequently Tool,
two-Tool, and effectful Tool E2E rows are `FAIL`, not merely environment-skipped.
Conditional and multi-turn native state workflows remain `UNSUPPORTED`.

## Exact invariants established below E2E

- Python and Go agree on the 20-byte public header layout and fixed 1,024-byte
  request frames.
- Header mutation, wrong profile/direction, replay, duplicate, and
  non-monotonic slot order are rejected in unit tests.
- U's input schema has no Agent/action/provider/payload/result/key field.
- Logical HANDOFF mutates only trusted kernel state.
- Pending results hold control state; early RETURN does not change the declared
  fixed profile constructed by the encoder.
- Go source/process-boundary tests show provider completion reaches the result
  ring, not a public socket send.
- EffectGate accepts one reservation per private operation ID.

These are component invariants. Because the full live path did not run,
`STRUCTURAL_PRIVACY` and `SIZE_PRIVACY` remain OPEN for canonical V3 rather than
PASS.

## Workflow matrix

`E2E_WORKFLOW_RESULTS.csv` contains all required families and distinguishes
`FAIL`, `UNSUPPORTED`, `NOT_RUN`, and `NOT_COMPLETED_ENVIRONMENT` explicitly.
`E2E_TRACE_MANIFEST.csv` lists every trace that actually exists and prohibits
citation of nonexistent Gateway traces.

## Phase-5 gate

Completed as a falsification/integration audit. Architecture integration is
PARTIAL, Gateway V2 integration is PARTIAL, and no canonical privacy experiment
is eligible to run in Phase 6.

