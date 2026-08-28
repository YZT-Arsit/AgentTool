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

- official SimplePIR-to-capsule-to-Control path: PASS (3/3 scheduled real/dummy
  queries correct in the canonical smoke run);
- private Cloud Slot Proxy schema and AEAD-bound public headers: unit PASS;
- corpus IR coverage: 3,574/7,386 = 48.39%; broad generality is not established;
- exact semantic fidelity: 54/72 = 75.0%; ordinary Tool loops fail;
- live Gateway V3 E2E: `NOT_COMPLETED_ENVIRONMENT` because Windows Application
  Control blocked the generated Pacer executable;
- structural, size, resource, and V3 timing privacy: OPEN; packet-level TCP
  timing: OPEN.

Start with `SYSTEM_INTEGRATION_FINAL_REPORT.md` and
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
.venv-stage10\Scripts\python.exe -m pytest tests -q
.venv-stage10\Scripts\python.exe scripts\run_corpus_ir_audit.py
.venv-stage10\Scripts\python.exe scripts\run_semantic_fidelity.py
```

`scripts/run_canonical_v3_pir_smoke.py` refuses to overwrite its existing
canonical output. Move/copy the output deliberately before a reproducibility
rerun. The live Gateway integration test explicitly skips only when Windows
reports Application Control WinError 4551.

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
