# AgentTool Canonical V3 Research Prototype

The sole active composition is defined by
`CANONICAL_ARCHITECTURE_V3.md` and `CANONICAL_THREAT_MODEL_V3.md`:

```text
official SimplePIR selection
    -> trusted Privacy/Control Kernel
    -> fixed encrypted control/action envelopes
    -> untrusted opaque Cloud Slot Proxy U
    -> CommonActionGateway V2
    -> trusted local model/Tool providers
    -> encrypted fixed result channel
```

Historical Stage 1-13 packages and reports are not parts to combine into this
architecture. Their current status is recorded in
`LEGACY_DEPRECATION_MANIFEST.md`. V1 `TIMING_NO_GO` evidence remains preserved.

## Current measured status

- immutable IR-v1 static coverage: 3,574/7,386 = 48.39%; immutable IR-v1
  semantic fidelity: 54/72 = 75.0%;
- IR-v2 core on the exact frozen corpus: 3,574/7,386 = 48.39% (no unsupported
  family was promoted); frozen dynamic fidelity: 72/72, including 18/18 Tool
  workflows;
- official SimplePIR path: PASS at N=1,000 in the canonical E2E and separately
  operational with full preprocessing at N=100,000;
- Linux canonical model -> Tool -> model, effectful Tool, and logical HANDOFF
  workflows: PASS for their declared bounded strata; dummy heavy operations: 0;
- real local GPU case study: PASS for one OpenAI-Agent-derived model -> Tool ->
  model workflow using Qwen2.5-0.5B-Instruct;
- structural and size privacy: PASS on the evaluated seven-workflow exact-trace
  subset and structural/size-only local falsification features;
- timing privacy: NOT TESTED on a valid reference platform; resource and
  packet-level privacy: OPEN.

Start with `SYSTEM_INTEGRATION_FINAL_REPORT_V2.md` and
`CURRENT_SECURITY_MATRIX.md`. Do not cite prior `FINAL_SECURITY_*` files as the
current model.

The active design does **not** use ORAM to hide Agent selection, dispatch, Tool
invocation, named endpoint activation, or execution identity. Retained Path
ORAM is an `OPTIONAL_PRIVATE_STATE_BACKEND` only.

## Local reproducibility

No external model or provider is contacted by these commands:

```text
set PYTHONPATH to:
  .venv-stage12/Lib/site-packages
  .venv-stage9/Lib/site-packages
  external_stage9/agent-framework/python/packages/core
  external_stage10/openai-agents-python/src
  repository root
```

```powershell
$env:PYTHONPATH = ".venv-stage12\Lib\site-packages;.venv-stage9\Lib\site-packages;external_stage9\agent-framework\python\packages\core;external_stage10\openai-agents-python\src;."
.venv-stage10\Scripts\python.exe -m pytest tests -q --basetemp .tmp_pytest_readme
.venv-stage10\Scripts\python.exe scripts\run_corpus_ir_audit.py
.venv-stage10\Scripts\python.exe scripts\run_semantic_fidelity_v2.py
```

Canonical evidence-producing scripts refuse to overwrite non-empty output
directories. Use a new versioned result directory for a reproduction. Linux is
the functional reference for the canonical process path; historical Windows
live-Pacer failures remain preserved and do not describe the Linux result.

## ORAM boundary

`src/path_oram.py` and authenticated/recovery descendants are retained only as
historical or optional outsourced-private-state experiments. The canonical
runner contains no mock lookup, Stage runtime, private-dispatch, or Path ORAM
import.

## Historical stages

Stage 1-13 artifacts are retained where they document other mediation-state,
storage, recovery, and timing experiments. Their former private-dispatch and
ORAM-backed invocation path is superseded and has been deleted; historical
results do not constitute evidence for the current full-domain target-privacy
goal.
