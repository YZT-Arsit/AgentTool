# Canonical AgentTool System Integration — Final Report V2

## Executive result

The bounded canonical path is operational on Linux, but the full research
system is **PARTIAL**, not an overall GO. A real framework Agent can be compiled
into IR-v2, recovered with the pinned official SimplePIR construction, executed
by the trusted Control Kernel, transported through an opaque fixed-frame Cloud
proxy and CommonActionGateway V2, invoke one real local Tool, reinsert its result
into a resumed model call, and return. The real GPU case study exercises the
same control/Gateway path.

The result is narrow. Corpus-scale static support remains 48.39%; Agent-as-Tool
is partial; runtime PIR fetch after handoff, durable effect reconciliation,
long-horizon privacy, timing, resource, and packet-level privacy remain open.

## Immutable negative baselines

- IR-v1 static corpus coverage: **3,574/7,386 = 48.39%**.
- IR-v1 semantic fidelity: **54/72 = 75.0%**.
- Gateway V1: **TIMING_NO_GO**.
- Gateway V2 Windows: **DEVELOPMENT_ONLY**.

No unsupported corpus instance was relabeled and no frozen failure artifact was
overwritten.

## Architecture exercised

```text
framework Agent definition
  -> IR-v2 compiler / fixed capsule
  -> trusted SimplePIR client role
  -> official SimplePIR server role
  -> trusted Control Kernel
  -> authenticated fixed frame
  -> untrusted opaque Cloud Slot Proxy
  -> CommonActionGateway V2
  -> one real local model or Tool primitive
  -> fixed result frame
  -> private control continuation / RETURN
```

The local experiment runs roles on one user-owned host. Process separation is
not claimed to protect against malicious host root; the security argument uses
the logical trust-domain split in `CANONICAL_THREAT_MODEL_V3.md`.

## IR and semantics

IR-v2 repairs explicit `MODEL -> TOOL_CALL -> TOOL_RESULT -> MODEL_RESUME ->
RETURN` semantics, including Tool identity, arguments, call ID, result, exact
private context reinsertion, bounded repetition, and private failure states.
The exact frozen 72-case set passes **72/72**, including **18/18** Tool
workflows. This does not convert the static corpus result: IR-v2 core remains
**3,574/7,386 = 48.39%** on the exact 314-file membership.

Eleven executable-support units fully pass their source-traceable gates. One
Agent-as-Tool unit is **PARTIAL**: an actual OpenAI `Agent.as_tool()` object is
compiled and the private child call stack executes, but native framework
call/return equivalence has not been run. Arbitrary callbacks, middleware,
HITL, fork/join, and general state systems remain unsupported/open.

## Real PIR path

The canonical N=1,000 workflow performs full preprocessing and three genuine
SimplePIR queries: one selected capsule and two reserved-row schedule queries.
All three recover correctly, fresh query encodings are used, and the
server-visible trace contains no private index or Agent label. Separate scale
runs physically instantiate N=100,000 with full preprocessing and correct
recovery.

At N=100,000, preprocessing is 23.507 s, mean online query/answer/recovery is
23.640 ms, upload/download are 36,388/37,180 bytes, and persistent client state
is 75.31 MB. The local bridge executes logically separated client/server roles
in one process; physical service separation remains an integration gap.

## Gateway, effects, and handoff

Read-only Tool, effectful Tool, and logical-handoff workflows all return with
semantic equality and zero dummy heavy operations. The effectful normal path
commits exactly one effect. New provider tests cover pre-effect timeout,
post-effect timeout, duplicate operation ID, provider error, and connection
interruption. Duplicate IDs execute once; however, post-effect timeout remains
an ambiguous outcome and the in-memory EffectGate is not durable across restart.

Logical handoff changes only the private logical Agent ID and retains the same
public Gateway endpoint. Both capsules are preloaded in this test. Fetching a
new capsule through the public PIR schedule on a cache miss remains open.

## Structural and size privacy

Seven Linux workflows differing in Agent/Tool identity, effect class, logical
handoff, and private branch state produce exactly the same public projection:
36 events, 18 request and 18 response frames, 1,024 bytes per frame, the same
slot/session order, and one `CommonActionGatewayV2` destination. No explicit
private field occurs in the Cloud trace.

A 42-episode offline sanity analysis also finds exact structural/size feature
equality. Both Logistic Regression and Random Forest report:

- 7-class Agent identity accuracy: **0.1429** (chance 1/7);
- Tool alpha/beta ROC-AUC: **0.5000**;
- private branch ROC-AUC: **0.5000**;
- 3-class action-family accuracy: **0.3333**.

Permutation p-values are 1.0. These classifiers do not prove security; exact
projection equality within the declared observer is the primary evidence.
Repeated-Agent, frequency, rare-event, transition, and cross-session attacks
remain **NOT TESTED** because no canonical long-horizon hidden-sequence workload
was executed.

## Real local LLM

One bounded OpenAI-Agent-derived workflow completes with genuine GPU inference
using `Qwen/Qwen2.5-0.5B-Instruct` at revision
`7ae557604adf67be50417f59c2c2f167def9a775`. It produces two model calls, one
exact local read-only Tool call, correct result reinsertion, final `RETURN`,
three real heavy operations, zero dummy heavy operations, and zero effects.
Two earlier failures—schema rejection and premature final output—are preserved.

This is real-flow external-validity evidence for one small model and one
workflow, not a model-quality or broad Agent-generalization claim.

## Profiles and cost

On the frozen dynamic-72 control-update proxy:

| Public profile | Fit | Overflow | Mean cover fraction | Bandwidth | Public duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| H4 / 1,024 B / 40 ms | 75% | 25% | 25.0% | 8,192 B | 160 ms |
| H6 / 1,024 B / 40 ms | 100% | 0% | 41.7% | 12,288 B | 240 ms |
| H8 / 1,024 B / 40 ms | 100% | 0% | 56.3% | 16,384 B | 320 ms |

These proxies exclude PIR, startup, and heavy provider latency. The live
real-model profile sends 262,144 public bytes over a 13.600 s computed schedule;
measured Gateway wall time is 14.279 s. Model generation averages 420.014 ms
per call and is not counted as privacy overhead. Detailed separated costs are
in `PERFORMANCE_REPORT.md`.

## TCB

The refreshed project runtime/integration surface is 24 files, 3,236 physical
LoC and approximately 2,913 nonblank/non-comment code LoC. Current compiler/E2E
tooling adds about 1,046 code LoC outside the online interpreter TCB. Pinned upstream
SimplePIR adds approximately 1,505 code LoC. Persistent PIR client state is
8.80 MB at N=1,000 and 75.31 MB at N=100,000. The trusted Gateway is material;
the honest description is a small control interpreter plus a larger trusted
mediation Gateway, not a few-hundred-line total TCB.

## Timing and platform gate

The Linux allocation is a Docker/cgroup-v2 environment with a 25-CPU quota,
recorded throttling, no permitted `SCHED_FIFO`, and no dedicated-core proof.
It is suitable for functional execution but not the frozen timing-confirmation
procedure. A development-only legacy V2 run also exposed a stale response-header
parse defect and produced no joinable receiver trace. No freeze manifest or
fresh holdout was created.

Therefore `TIMING_PRIVACY = NOT_TESTED / OPEN`. Resource privacy and TCP
packet-level timing remain OPEN.

## Regression and hygiene

- Canonical/local Python suite: **156 passed, 1 legacy V2 test deselected**.
- Unfiltered local suite: **156 passed, 1 failed**; the failure is the preserved
  legacy `gateway_v2` Linux-style socket-trace join defect, not the canonical
  `cloud_slot_proxy` path.
- CommonActionGateway V2 Go suite: **PASS**.
- Earlier remote focused IR-v2/canonical suite: **19 passed**; remote Go suite:
  **PASS**.

The legacy failure is documented in `LEGACY_DEPRECATION_MANIFEST.md` and is not
silently called a passing regression.

## Independent final statuses

```text
ARCHITECTURE_INTEGRATION: PARTIAL
REAL_PIR_PATH: PASS
PRIVATE_CONTROL_PLACEMENT: PASS
MODEL_TOOL_MODEL_SEMANTICS: PASS (validated bounded strata)
IR_V1_STATIC_COVERAGE: 48.39% [immutable historical baseline]
IR_V2_STATIC_COVERAGE: 48.39% [same frozen 314-file corpus]
IR_V2_EXECUTABLE_SEMANTIC_SUPPORT: 72/72 frozen executions; 11 full units + 1 PARTIAL unit
IR_V1_SEMANTIC_FIDELITY: 75.0% [immutable historical baseline]
IR_V2_SEMANTIC_FIDELITY: 100.0% (72/72)
TOOL_WORKFLOW_FIDELITY: 100.0% (18/18)
PROFILE_FEASIBILITY: H4 75% fit/25% overflow; H6/H8 100% fit/0% overflow
TCB: ~2,913 project runtime/integration code LoC + ~1,505 upstream SimplePIR code LoC
FIXED_TRANSCRIPT: PASS (evaluated subset)
GATEWAY_V2_INTEGRATION: PARTIAL (functional PASS; timing/effect durability open)
REAL_LOCAL_LLM_E2E: PASS (one bounded workflow)
STRUCTURAL_PRIVACY: PASS (evaluated seven-workflow structural observer)
SIZE_PRIVACY: PASS (evaluated seven-workflow structural observer)
TIMING_PRIVACY: NOT_TESTED / OPEN
RESOURCE_PRIVACY: OPEN
PACKET_LEVEL_TIMING: OPEN
DUMMY_HEAVY_OPS: 0
```

## Strongest negative findings

1. Static generality did not improve: 51.61% of behavior instances remain
   unsupported on the frozen corpus.
2. No valid Linux timing-reference or fresh holdout result exists.
3. Long-horizon target/frequency/transition privacy, durable effects, and
   runtime handoff lookup are unclosed.

The scientifically defensible conclusion is a functioning bounded canonical
prototype with exact structural/size evidence, not a complete agent-trajectory
privacy system.

## Evidence integrity

Transfer archive SHA-256 values:

- successful real-LLM run:
  `0b13959d1b18f5797ae5e12e90dba207c473c44dc4ab62d938cfe93995d8dec8`;
- preserved failed LLM attempts:
  `06c55f49b92656483ab98e640ca9ba480998b2a3f39b56b0f191525abc3d5960`;
- extended structural/size run:
  `72fae0b644c081223830c4b116a863fbcb091de1f0a13e39520070fe16db5281`;
- structural/size falsification run:
  `f64fd8de066ddbb3e18f74c1c37dd9637b15aa830e0940754f10b3d60962cdef`;
- failed Linux timing-development artifact:
  `09505f321f60ee05d8389c0efe0c747aabcffe167a7209ce56dad154c6bb1935`.
