# System Integration Final Report

## Executive result

The repository now has one documented canonical V3 composition and a concrete
trusted/untrusted interface implementation. It is **not a completed privacy
system**. Real SimplePIR closure and component invariants pass, but full Gateway
execution is blocked by host policy, corpus generality is low, and ordinary
Tool semantics fail exact dynamic comparison.

No overall GO/NO-GO label is assigned; dimensions are reported independently.

## Canonical dataflow

```text
trusted SimplePIR client
  -> private capsule cache / Control Kernel
  -> fixed AES-GCM envelope (public header authenticated)
  -> untrusted opaque Cloud Slot Proxy U
  -> one CommonActionGateway V2 tunnel
  -> trusted Worker / local provider / EffectGate
  -> fixed encrypted RESULT or WAIT
  -> trusted Control Kernel result consumer
```

The complete line above is implemented in source. Only the
SimplePIR-to-Control prefix and unit-level Gateway/proxy contracts executed on
this host; the live Pacer process was blocked.

## Integration/security status

```text
ARCHITECTURE_INTEGRATION: PARTIAL
REAL_PIR_PATH: PASS
PRIVATE_CONTROL_PLACEMENT: PASS
FIXED_TRANSCRIPT: PASS (component/unit); OPEN end to end
GATEWAY_V2_INTEGRATION: PARTIAL
AGENT_IR_GENERALITY: 48.39% (3,574/7,386 behavior instances)
SEMANTIC_FIDELITY: 75.0% (54/72 exact executions)
STRUCTURAL_PRIVACY: OPEN
SIZE_PRIVACY: OPEN
TIMING_PRIVACY: NOT_TESTED
RESOURCE_PRIVACY: OPEN
PACKET_LEVEL_TIMING: OPEN
DUMMY_HEAVY_OPS: 0 in completed canonical component runs; NOT MEASURED end to end
```

### Architecture integration — PARTIAL

Canonical packages and a single runner exist. U receives only an opaque frame
queue and public profile; the trusted kernel owns plaintext and result
decryption. The complete process graph did not execute because Windows
Application Control blocked `gateway-pacer.exe` (WinError 4551).

### Real PIR path — PASS

The pinned official SimplePIR bridge at
`e9020b03bf2872c75b8954e749e32408b5db87ed` ran full preprocessing over a
physically instantiated 1,000-row/1,024-byte registry. One needed lookup and two
reserved-row dummy slots were all real queries: 3/3 recovered correctly, raw
queries were fresh, and the server-visible trace contained no private index,
class, or Agent field. The needed capsule directly enabled a trusted control
transition. This run does not replace the prior separately reported 100K
scalability measurement.

### Private control placement — PASS

The new `privacy_kernel/` is the only canonical plaintext descriptor encoder and
response consumer. `cloud_slot_proxy/` has no key/private field in its schema.
Logical HANDOFF changes only trusted state. Pending results/lookups prevent
private progress while the public profile remains fixed.

### Fixed transcript — component PASS, system OPEN

Go/Python unit tests establish fixed widths, authenticated profile/session/slot
headers, monotonic sequence enforcement, logical-only handoff, pending-state
holding, and public-horizon construction. No full U/Gateway trace exists, so
these do not support an end-to-end structural or size privacy PASS.

### Agent-IR generality — limited

The import-free AST audit scanned 314 pinned local files (216 OpenAI examples;
98 locally available Microsoft sample/core-test files), zero parse errors, 576
constructor instances, 328 workflow instances, and 7,386 behavior instances.
Only 48.39% are compiled or shared primitives. Largest unsupported classes are
state/memory (1,589), middleware (932), arbitrary conditional edges (738),
loops (165), fan-out/fan-in (156), HITL/resume (143), and Agent-as-Tool (61).
Constructor instances are not unique authored Agents.

### Semantic fidelity — 75.0%

Exact native-versus-compiled projections pass for OpenAI simple, OpenAI
logical-handoff, and Microsoft simple strata (54 executions). All 18 ordinary
OpenAI Tool executions fail: the compiler emits no post-Tool LLM transition,
loses exact arguments/effect projection, and stalls after `TOOL_RESULT`.
This is a method blocker for Tool-heavy claims, not an environment limitation.

### Gateway/effect robustness

Protocol and EffectGate unit tests pass. Public metadata is bound as AEAD AAD;
malformed/direction/profile/replay/duplicate/order errors are rejected.
Operation IDs are accepted once by the trusted effect gate. Provider timeout,
post-request ambiguity, restarts, saturation, and late-result behavior were not
executed through the canonical tunnel and remain OPEN.

## Phase-7 timing discipline

The host is Windows, not the Linux reference platform. No calibration,
configuration freeze, or confirmatory timing dataset was generated. The V1
`TIMING_NO_GO` result remains valid historical failure evidence; the V2 Windows
development run remains `DEVELOPMENT_ONLY`. The current Gateway code
cross-builds for Linux, but a cross-build is not timing evidence. TCP
packet-level timing remains OPEN.

## Regression evidence

- Python: **137 passed, 2 skipped** in 47.57 s. Both skips explicitly identify
  WinError 4551 for the local Pacer executable; no other test was skipped.
- Go: all `common_action_gateway_v2` tests pass, including authenticated header,
  sequence/replay, fixed-allocation response preparation, rings, and EffectGate.
- Linux cross-build: PASS (`GOOS=linux`, `GOARCH=amd64`, `CGO_ENABLED=0`).

The skipped integration tests mean regression correctness is PASS for executable
components and OPEN for the live canonical Gateway path.

## Required next work

1. Repair the IR semantics first: add a bounded model/Tool loop and explicit
   protected Tool argument/result flow, then repeat exact native comparisons.
2. Run the unchanged canonical process graph on an authorized Linux host where
   the Pacer executable is permitted; complete E2E correctness and failure
   injection before privacy classifiers.
3. Only after E2E success, collect U-only structural/size/resource views and run
   the predeclared local distinguishability evaluation.
4. Timing requires isolated Linux calibration, a frozen configuration/margin,
   and an untouched confirmatory holdout. No Windows or historical trace may be
   promoted to that result.

## Claim boundary

Current evidence supports a narrower engineering statement: real private
capsule selection can feed a trusted logical-control kernel, and the proposed
opaque fixed-frame Gateway interface is implementable and unit-checkable. It
does not yet support end-to-end Agent trajectory privacy, general Agent
compilation, ordinary Tool semantic preservation, timing privacy, resource
privacy, or packet-level privacy.

