# AgentTool Canonical V6 Action-Metadata Privacy Prototype

The sole active composition is defined by `CANONICAL_ARCHITECTURE_V6.md`,
`V6_THREAT_MODEL.md`, and `CURRENT_SECURITY_DEFINITION_V6.md`:

```text
orthogonal protected payload pipeline -> ProtectedActionIntent
    -> TrustedActionModule (local functional backend; future TEE/CVM)
    -> resident capability-to-ID map
    -> official SimplePIR over encrypted AgentDescriptorV6 rows
    -> fixed encrypted ActionCellV6
    -> opaque cloud client (no private workload or key)
    -> CommonActionGateway V2
    -> trusted route resolution -> real provider action
```

Agent Control IR is no longer canonical: `CANONICAL_IR_DEPENDENCY = NONE`.
Historical IR and Stage 1-13 artifacts remain frozen evidence, classified in
`IR_DEPRECATION_V6.md` and `LEGACY_DEPRECATION_MANIFEST_V6.md`. V1
`TIMING_NO_GO` remains preserved.

## Current measured status (V6)

- encrypted official SimplePIR descriptor path: PASS at 1K/10K/100K with full
  preprocessing and correct authenticated recovery;
- 100K: 100,000 logical / 100,001 physical rows, 34.4 s preprocessing,
  approximately 52.2 ms online query+answer+recovery, 75.3 MB client state;
- action-mediation corpus: 894/1,370 (65.26%) fully mediated, 473 PARTIAL, 3
  unsupported; static audit only;
- fresh outbound-action semantic holdout: 16/16 once across both pinned
  frameworks;
- local trusted module: functional PASS; hardware attestation and memory
  confidentiality NOT TESTED; rollback OPEN;
- live V6 Gateway: PARTIAL. One development arm delivered 43/50 results and the
  next run was blocked by host Application Control. STRICT structural, size,
  and long-horizon privacy remain OPEN;
- timing and packet-level timing: OPEN / NOT TESTED; resource privacy: OPEN;
- dummy heavy operations: 0.

Start with `FINAL_SYSTEM_AUDIT_V6.md`. The V5 section below is retained only as
historical context and must not be read as the active architecture.

## Historical V5 status

- immutable IR-v1 static coverage: 3,574/7,386 = 48.39%; immutable IR-v1
  semantic fidelity: 54/72 = 75.0%;
- IR-v2 core on the exact frozen corpus: 3,574/7,386 = 48.39% (no unsupported
  family was promoted); the prior 72/72 dynamic result, including 18/18 Tool
  workflows, is now classified as **development regression evidence** because
  those cases informed the semantic repair;
- untouched semantic holdout: incomplete (8 valid passes, 12 harness-invalid
  cases preserved without rerun); this is not a new fidelity rate;
- new source-traceable semantic holdout V3: 12/12 once, supporting only its
  bounded model/Tool/handoff strata; it does not replace the frozen corpus metric;
- official SimplePIR path: PASS at N=1,000 in the canonical E2E and separately
  operational with full preprocessing at N=100,000;
- Linux canonical model -> Tool -> model, effectful Tool, and logical HANDOFF
  workflows: PASS for their declared bounded strata; dummy heavy operations: 0;
- real local GPU case study: PASS for one OpenAI-Agent-derived model -> Tool ->
  model workflow using Qwen2.5-0.5B-Instruct;
- repaired continuation and horizon development: STANDARD/LONG complete one
  three-operation workflow; SHORT fails and remains preserved; this is not a
  long-horizon privacy result;
- structural and size privacy: PASS only on the earlier evaluated seven-workflow
  development subset. The frozen eight-family transport shapes were exactly
  equal with grouped AUC 0.5, but the whole-workflow E2E gate **failed** (zero
  delivered results; workflows never returned), so long-horizon privacy remains open;
- timing privacy: NOT TESTED on a valid reference platform; resource and
  packet-level privacy: OPEN.
- hardware TEE attestation: NOT TESTED. `confidential_v5` provides a functional
  local trusted-process backend only and makes no malicious-host isolation claim.
- cryptographic PSI: NOT IMPLEMENTED; local in-TEE membership is implemented,
  and PSI is unnecessary when the full enterprise catalog is resident there.

Start with `FINAL_SYSTEM_AUDIT_V5.md` and `CANONICAL_ARCHITECTURE_V5.md`. V3/V4
documents remain evidence records and must not be cited as the active trust model.

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
