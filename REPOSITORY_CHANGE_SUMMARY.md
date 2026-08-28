# Repository change summary

## Active-path migration

The active design now lives in `agent_control_virtualization/` and
`scripts/run_control_virtualization.py`. It contains no ORAM import and exposes
one physical `AgentControlExecutor` plus one `ToolExecutionAdapter` boundary.

## Deleted rejected implementation

| Deleted path | Reason |
| --- | --- |
| `stage11_core_redesign/routing.py` | Implemented direct/PIR/ORAM/full-cover named dispatch variants. |
| `stage11_core_redesign/experiment.py` | Drove the rejected routing experiment. |
| `scripts/run_stage11.py` | Stale CLI for the rejected dispatch path. |
| `tests/test_stage11.py` | Asserted obsolete ORAM/full-cover dispatch behavior. |
| `results_stage11/routing_privacy.csv` | Generated rejected-dispatch results. |
| `results_stage11/routing_scaling.csv` | Generated rejected-dispatch results. |
| `results_stage11/stage11_summary.json` | Mixed rejected routing with other Stage-11 results. |
| `results_stage11/final_console_summary.txt` | Reported the superseded routing decision. |
| `results_stage12/private_dispatch.csv` | Generated full-cover dispatch result. |
| `results_stage12/routing_summary.csv` | Generated full-cover summary. |
| `PRIVATE_AGENT_DISPATCH_DESIGN.md` | Described the rejected dispatch candidate. |
| `PRIVATE_DISPATCH_SUPPORTING_RESULTS.md` | Reported the rejected full-cover path. |
| `FINAL_ROUTING_PRIOR_ART_AUDIT.md` | Bound to the superseded routing proposal. |
| `ROUTING_PRIOR_ART_MATRIX.csv` | Bound to the superseded routing proposal. |
| `FINAL_SCOPE_GATE.md` | Selected private dispatch as a component. |
| `FINAL_EXPERIMENT_MATRIX.md` | Scheduled obsolete ORAM/full-cover routing experiments. |
| `STAGE11_CORE_METHOD_REPORT.md` | Mixed the rejected routing path into the method decision. |

`stage12_final_p0/supporting.py`, `stage12_final_p0/summarize.py`, and
`tests/test_stage12.py` were edited to remove the full-cover dispatch function,
invocation, aggregation, and test. `stage11_core_redesign/__init__.py` no longer
exports routing symbols.

## Retained ORAM classification

`src/path_oram.py` is retained as `OPTIONAL_PRIVATE_STATE_BACKEND` because older
experiments use it to simulate access to independent persistent private state.
Its module warning and the root README prohibit using it for Agent selection,
dispatch, Tool invocation, or named execution identity. Historical storage,
recovery, and timing code remains archival and is not imported by the active
package.

## New files

- `agent_control_virtualization/{ir,compiler,framework_fixtures,lookup,runtime,experiment}.py`
- `scripts/run_control_virtualization.py`
- `tests/test_control_virtualization.py`
- `results_control_virtualization/` raw outputs
- architecture, IR, coverage, lookup, privacy, cost, falsification, lower-bound,
  and final-decision reports listed in the root README

No final paper text was rewritten.
