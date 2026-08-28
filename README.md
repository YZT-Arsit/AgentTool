# Agent Control Virtualization Feasibility Audit

The active experiment asks whether framework-native Agent control can be
represented as private data consumed by one common physical executor. It does
**not** use ORAM to hide Agent selection, dispatch, Tool invocation, named
endpoint activation, or execution identity.

The active path is:

```text
PrivateAgentLookup(index)
    -> fixed-width private Agent capsule
    -> AgentControlExecutor
    -> fixed interaction frames
    -> one real shared heavy primitive
```

The active closure path uses official `ahenzinger/simplepir` at commit
`e9020b03bf2872c75b8954e749e32408b5db87ed`. The deliberately named
`MOCK_PRIVATE_LOOKUP_NON_CRYPTOGRAPHIC` remains only as a historical/direct
leakage baseline and is not used by the B2 closure experiment.

Run locally, without model or network calls:

```powershell
$env:PYTHONPATH = ".venv-stage9\Lib\site-packages;external_stage9\agent-framework\python\packages\core;external_stage10\openai-agents-python\src;."
.venv-stage10\Scripts\python.exe -m pytest tests\test_control_virtualization.py tests\test_crypto_closure.py -q
.venv-stage10\Scripts\python.exe scripts\run_control_virtualization.py
```

Control-virtualization outputs are isolated in `results_control_virtualization/`;
cryptographic and repeated-observation outputs are in
`results_crypto_closure/`. Start with
`CRYPTOGRAPHIC_CLOSURE_FINAL_REPORT.md` and `FINAL_SECURITY_MATRIX.md`.

## ORAM boundary

`src/path_oram.py` and authenticated/recovery descendants are retained only as
historical or `OPTIONAL_PRIVATE_STATE_BACKEND` experiments for outsourced
private records. They are not imported by the active control-virtualization
package and must not be cited as hiding activation of a fixed Agent or Tool API.

## Historical stages

Stage 1-13 artifacts are retained where they document other mediation-state,
storage, recovery, and timing experiments. Their former private-dispatch and
ORAM-backed invocation path is superseded and has been deleted; historical
results do not constitute evidence for the current full-domain target-privacy
goal.
