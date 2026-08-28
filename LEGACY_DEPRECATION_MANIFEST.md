# Legacy Deprecation Manifest

This manifest records reachability decisions before code cleanup. “Preserved”
means reproducibility evidence remains on disk; it does not mean the component
is reachable from the canonical V3 entrypoint.

| Legacy family | Classification | Action | Reason |
| --- | --- | --- | --- |
| `MockPrivateLookup` and `agent_control_virtualization/experiment.py` lookup scaling | SUPERSEDED | Preserve for historical tests; prohibit canonical import | Non-cryptographic and previously leaked target identity |
| Stage 11 private dispatch, visible cover, and removed routing code/results | SUPERSEDED / ARCHIVED | Keep existing deletion record and remaining reports only | Visible named subsets cannot meet full-domain privacy without linear cover |
| ORAM-as-Agent/Tool invocation or selection claims | REJECTED | No active implementation may use or describe this path | Fixed named activation is not a rerandomizable physical address |
| `src/path_oram.py`, durable ORAM, modular/unified storage experiments | OPTIONAL_PRIVATE_STATE_BACKEND / HISTORICAL | Preserve; no canonical imports | Only applicable to outsourced persistent-state access patterns |
| `timing_closure/` and `timing_closure_native/` V1 Gateway | VALID FAILED BASELINE | Preserve code, reports, raw `confirmatory_final_*` traces, and hashes; no canonical imports | Frozen `TIMING_NO_GO` demonstrates workload-correlated release jitter |
| `stage12_final_p0/` and `stage13_timing_repair/` | SUPERSEDED EXPERIMENTS | Preserve; no canonical entrypoint | Earlier application/runtime shaping and five-slot tests are not the final transport/system model |
| `stage8_real_traces/`, `stage9_adaptive/`, `stage10_final_validation/`, `stage11_core_redesign/` | ARCHIVED STAGE EXPERIMENTS | Preserve; no canonical imports | Historical research questions and evidence, not V3 composition |
| `scripts/run_stage*.py` | SUPERSEDED ENTRYPOINTS | Preserve for reproducibility; exclude from README current-run instructions and canonical smoke tests | Prevent accidental mixed-stage execution |
| `scripts/run_control_virtualization.py` | VALID HISTORICAL FEASIBILITY ENTRYPOINT | Preserve; not canonical after V3 runner exists | Uses mock lookup in non-closure experiments |
| `scripts/run_gateway_v2_development.py` | VALID HISTORICAL DEVELOPMENT ENTRYPOINT | Preserve; not canonical system runner | Loads private workload in the old client and is Windows development evidence only |
| `FINAL_SECURITY_DEFINITION.md`, `FINAL_SECURITY_DEFINITION_V2.md`, `FINAL_SECURITY_DEFINITION_AUDIT.md`, `FINAL_SECURITY_AUDIT.md` | SUPERSEDED SECURITY DEFINITIONS | Preserve verbatim and label through this manifest; canonical reports cite only `CURRENT_SECURITY_*` | Definitions reflect earlier dispatch/ORAM/timing boundaries |
| Stage-generated result directories | ARCHIVED OR VALID HISTORICAL EVIDENCE | Never merge into V3 results; do not overwrite | Preserve positive and negative reproducibility evidence |

## Cleanup rule

No legacy source or result is deleted solely to simplify a privacy claim. Code
is removed only when it is dead, its role is documented above, regression tests
confirm no valid historical artifact depends on it, and failure evidence remains
available. Canonical source tests include an import/reachability check.

## Frozen evidence protections

- V1 timing reports and raw traces remain historical `TIMING_NO_GO` evidence.
- Official SimplePIR standalone results remain scalability/primitive evidence,
  not proof of end-to-end V3 privacy.
- The 22-Agent/85-behavior audit remains feasibility evidence, not corpus-scale
  generality evidence.
- Windows V2 development timing remains `DEVELOPMENT_ONLY`.

## Phase-0 completion gate

PASS. No code or result was deleted, no experiment was run, and all known legacy
families now have an explicit canonical reachability decision.

