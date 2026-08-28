# Canonical Component Status

Snapshot: 2026-08-27, after Phase 0 inventory and before V3 experiments.

| Component / artifact | Status | Canonical role or restriction |
| --- | --- | --- |
| `CANONICAL_ARCHITECTURE_V3.md` | CANONICAL ACTIVE | Sole architecture composition guide |
| `CANONICAL_THREAT_MODEL_V3.md` | CANONICAL ACTIVE | Sole current observer boundary |
| `common_action_gateway_v2/` Worker/Pacer/rings/providers | CANONICAL ACTIVE, REQUIRES HARDENING | Preserve process isolation and pacing; add authenticated public header and trusted/proxy split |
| `gateway_v2/` orchestration | CANONICAL ACTIVE, REQUIRES REFACTOR | Reuse local process orchestration; remove private workload/key from U |
| `agent_control_virtualization/ir.py` and compiler concepts | CANONICAL INPUT, REQUIRES EXTENSION | Fixed capsule/IR basis; corpus extractor and semantic tests decide actual coverage |
| `agent_control_virtualization/runtime.py` | VALID SEMANTIC REFERENCE | Plaintext evaluator is not an untrusted-cloud security component |
| `privacy_kernel/` | CANONICAL ACTIVE, TO IMPLEMENT | Trusted PIR client, control kernel, encoder, and result consumer |
| `cloud_slot_proxy/` | CANONICAL ACTIVE, TO IMPLEMENT | Opaque public-slot forwarding only |
| `pir_integration/simplepir_bridge/` | CANONICAL ACTIVE PRIMITIVE | Pinned official SimplePIR bridge; must feed canonical path |
| `cryptographic_closure/pir_backend.py` | VALID INTEGRATION REFERENCE | Reuse audited invocation/provenance; private CSV trace is trusted-only |
| trusted/local encrypted state | CANONICAL BASE | Private persistent-state profile |
| `src/path_oram.py`, `system_stage6/`, `system_stage7/` | OPTIONAL_PRIVATE_STATE_BACKEND / HISTORICAL | Never Agent/Tool invocation privacy |
| V2 Windows development artifacts | VALID HISTORICAL DEVELOPMENT | Engineering evidence only; no timing-privacy conclusion |
| V1 `TIMING_NO_GO` artifacts under `results_timing_closure/` | VALID HISTORICAL BASELINE | Immutable failure/reproducibility evidence |
| `MockPrivateLookup` | SUPERSEDED BASELINE ONLY | Forbidden from canonical imports/entrypoints |
| Stage 11 full-cover/private-dispatch results | SUPERSEDED / ARCHIVED | May motivate costs; not canonical architecture |
| Stage 1-10 mediation/ORAM experiments | ARCHIVED RESEARCH EVIDENCE | No canonical execution imports |
| Stage 12-13 application-level timing work | SUPERSEDED TIMING EVIDENCE | Does not establish V3 observer-boundary timing privacy |
| old `FINAL_SECURITY_DEFINITION*.md` family | SUPERSEDED | Preserved verbatim; replaced by `CURRENT_SECURITY_*` |

## Canonical reachability rule

The eventual canonical entrypoint may import only the V3 Privacy Kernel,
opaque Cloud Slot Proxy, Gateway V2, official SimplePIR integration, selected
IR/compiler modules, and local provider adapters. It must not import mock lookup,
private dispatch/full cover, Stage runtime packages, or Path ORAM. Tests may
continue importing historical code to preserve reproducibility.

## Phase-0 completion gate

PASS. The architecture, threat boundary, initial component classifications,
and legacy preservation/deprecation rules are documented. No new experiment was
run during Phase 0.

## Phase-1 implementation audit

Completed source work:

- protocol version 3 authenticates version, direction, public session, public
  slot, and profile ID as AEAD associated data;
- Go and Python validators reject malformed, wrong-profile, wrong-direction,
  replayed, duplicate, and non-monotonic frames;
- canonical key provisioning uses a restricted ephemeral key file, passes only
  its path to trusted Gateway processes, never gives a key to U, and removes the
  file after a run;
- `privacy_kernel/` now owns plaintext descriptors, capsule/control state,
  encryption, and result decryption;
- `cloud_slot_proxy/` is a distinct process whose schema contains only address,
  public profile, host-log path, and opaque fixed frames;
- the asynchronous Control Kernel holds state while a result or capsule is
  pending, implements logical-only HANDOFF, and continues cover after RETURN;
- the trusted Worker has an operation-ID EffectGate and explicit local model,
  read-only Tool, and effectful Tool provider classes.

Validation completed: Go protocol/effect-gate tests pass; Python trust-boundary,
header-integrity, pending-state, logical-HANDOFF, and canonical-reachability
tests pass. The first full local process launch was blocked specifically when
Windows Application Control refused the newly generated `gateway-pacer.exe`
(WinError 4551). No bypass was attempted. Therefore the live V3 result-consumer
path is `NOT_COMPLETED_ENVIRONMENT` on this host and remains a Phase-2 execution
gate rather than a claimed PASS.

## Phase-2 integration audit

The canonical trusted lookup scheduler executed three genuine queries through
the pinned official `ahenzinger/simplepir` bridge at commit
`e9020b03bf2872c75b8954e749e32408b5db87ed`: one real capsule selection and two
reserved-row dummy selections. Full preprocessing ran, all 3 records recovered
correctly, raw queries were distinct, and the server-visible trace contained no
private index/class/Agent field. The recovered capsule was installed directly
in the Control Kernel and enabled its first transition. Evidence is isolated in
`results_canonical_v3/phase2_pir_smoke/`.

`REAL_PIR_PATH` is PASS for this functional schedule. The complete
PIR-to-Control-to-Proxy-to-Gateway-to-provider-to-result-consumer execution is
`NOT_COMPLETED_ENVIRONMENT`: Windows Application Control still blocks the local
Pacer executable. Consequently `GATEWAY_V2_INTEGRATION` remains PARTIAL and no
live end-to-end privacy result is claimed.

## Phase-3 corpus audit

PASS as a measurement. The import-free AST extractor scanned 314 pinned local
Python files with zero parse errors and recorded 7,386 control-behavior
instances. Current `COMPILED + SHARED_PRIMITIVE` coverage is 3,574/7,386 =
48.39%; 3,812 instances remain unsupported. This is evidence against broad
Agent-IR generality and supersedes the earlier 22-object/95.3% feasibility
number for corpus-scale claims. See `CORPUS_IR_AUDIT.md` and the three canonical
CSV artifacts.

## Phase-4 semantic-fidelity audit

Completed 72 local native-versus-compiled executions across OpenAI simple,
OpenAI Tool, OpenAI handoff, and Microsoft simple strata. Exact fidelity is
54/72 = 75.0%. All simple and logical-handoff runs matched; all 18 ordinary
OpenAI Tool runs failed because the current compiler omits the post-Tool model
transition and protected argument/result semantics. No result was hidden or
converted to textual similarity. See `SEMANTIC_PRESERVATION_REPORT.md`.

## Phase-5 end-to-end audit

No full canonical E2E workflow completed. The real PIR-to-Control prefix is
executed, but Windows Application Control prevents the Gateway Pacer from
starting. Separately, ordinary Tool workflows fail exact compiler semantics.
The required workflow and trace manifests record these outcomes without
fabricating missing measurements. Canonical structural/size privacy therefore
remain OPEN.

## Phase-6 ablation and resource audit

Completed without a new classifier run. The B0-B5 ladder separates real
SimplePIR, control placement, fixed transcript, historical V1 failure, and the
environment-incomplete V3 row. Resource features were reclassified by actual
observer ownership; no U resource trace exists, so `RESOURCE_PRIVACY` is OPEN.
The canonical security definition/assumptions/matrix now replace earlier
security-definition variants for current claims.

## Phase-7 and final audit

The current host is Windows. Per the frozen discipline, no Linux timing
calibration or confirmatory timing run was attempted. Gateway V2 cross-builds
for Linux, but timing and TCP packet-level timing remain OPEN/NOT_TESTED.

Final regression result: 137 Python tests passed and exactly two live-Pacer tests
were skipped as `NOT_COMPLETED_ENVIRONMENT` for Windows Application Control
WinError 4551. All Go tests passed, and the Linux cross-build passed. Final
independent dimension statuses are in `SYSTEM_INTEGRATION_FINAL_REPORT.md`.
