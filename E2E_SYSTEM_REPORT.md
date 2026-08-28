# Canonical V3 end-to-end system report

## Result

The Linux canonical path is **operational for the validated single-Tool stratum**. One source-traceable OpenAI Agents SDK `Agent` and `FunctionTool` were compiled under IR-v2, serialized into a 1,000-row registry, recovered through the pinned official SimplePIR implementation, installed in the trusted `ControlKernel`, and executed through the opaque Cloud Slot Proxy and CommonActionGateway V2. The Gateway result was consumed by the kernel, reinserted into private model context, and followed by a second model call and `RETURN`.

This is not corpus-wide architecture integration. It does not establish
arbitrary multi-Tool lowering, runtime PIR fetch on handoff, long-horizon
repeated-observation privacy, timing privacy, resource privacy, or packet-level
timing.

## Executed path

```text
OpenAI Agents SDK Agent + FunctionTool
  -> IR-v2 compiler audit
  -> strict single-Tool canonical lowering
  -> 1,000 x 1,024-byte capsule registry
  -> official SimplePIR full preprocessing and three scheduled queries
  -> recovered capsule installed in trusted ControlKernel
  -> MODEL request
  -> fixed encrypted frame
  -> opaque Cloud Slot Proxy
  -> CommonActionGateway V2
  -> local HTTP model emulator
  -> structured TOOL_CALL(name, arguments, call_id)
  -> local read-only Tool
  -> TOOL_RESULT reinserted into private model context
  -> second model request
  -> FINAL
  -> RETURN
```

## Real PIR evidence

- Backend: `OFFICIAL_SIMPLEPIR_FULL_PREPROCESSING`
- Pinned commit: `e9020b03bf2872c75b8954e749e32408b5db87ed`
- Correct queries: 3/3 (one real, two scheduled dummy-row queries)
- Fresh query encodings: yes
- Private index in server-visible trace: no
- Full preprocessing: 112.367 ms for the 1,000-row E2E registry
- Query upload: 2,020 bytes/query; answer download: 6,592 bytes/query
- Persistent client state: 8,798,208 bytes

The cryptographic privacy claim derives from SimplePIR, not from a classifier. In
this local bridge, client and server algorithm roles execute in one Go process
while producing separate client-private and server-visible traces; physical
process/network separation remains an integration gap. This E2E run is a
correctness/cryptographic-execution test at 1,000 rows; the separately frozen
100K PIR results remain the scale evidence.

## Control semantics

The private kernel observed the exact sequence:

1. user context;
2. `TOOL_CALL(READ_ONLY_TOOL, {"topic":"synthetic-local"}, call-op-00000001)`;
3. `TOOL_RESULT(call-op-00000001, READ_ONLY_TOOL:0)`;
4. result reinsertion into the next model context;
5. final result `completed:READ_ONLY_TOOL:0`;
6. `RETURN`.

The final state had an empty failure class. Three real heavy operations occurred (model, Tool, resumed model); dummy heavy operations were zero.

## Additional Linux workflows

| Workflow | Real heavy operations | Effects | Returned | Dummy heavy operations | Semantic check |
| --- | ---: | ---: | --- | ---: | --- |
| LLM read Tool | 3 | 0 | yes | 0 | pass |
| LLM effectful Tool | 3 | 1 | yes | 0 | pass |
| Logical handoff | 1 | 0 | yes | 0 | pass |

The handoff changed private logical Agent ID from 20 to 21 while retaining the same public `CommonActionGatewayV2` destination. In this test both capsules were preinstalled; runtime PIR fetch on a cache miss remains unfinished.

## Cloud-observer audit

Each workflow produced 18 request and 18 response observations. Every frame was 1,024 bytes and used one public destination. Searches of the serialized Cloud traces found no `logical_agent`, provider, operation ID, opcode, payload, result, or key fields. The trusted kernel, Worker, Pacer, proxy, and three providers had distinct process IDs.

The previous run's `reference_timing_platform: true` field was a diagnostic bug: it was set solely from the Linux build tag. The source has been repaired so a timing-reference label requires both applied affinity and applied real-time scheduling. The old run remains integration evidence but is not timing evidence.

## Current status

- Model–Tool–Model semantics: **PASS for the validated single-Tool stratum**
- Official PIR feeding the actual kernel/Gateway path: **PASS at N=1,000**
- Result feedback into control: **PASS**
- Effectful Tool once-only outcome in the completed run: **PASS**
- Effect/provider failures: **PARTIAL**; timeout/error/interruption remain
  private and duplicate IDs execute once, but timeout-after-effect and durable
  restart reconciliation remain open
- Logical handoff through one physical endpoint: **PASS with preloaded capsule limitation**
- Corpus-wide executable support: **OPEN**
- Runtime handoff PIR fetch: **OPEN**
- Structural/size privacy: **PASS on the evaluated seven-workflow Linux subset**;
  42-episode structural/size-only classifier sanity checks are at chance
- Long-horizon repeated/frequency/rare/transition privacy: **NOT TESTED**
- Real local GPU model flow: **PASS on one bounded workflow**
- Linux timing privacy: **NOT TESTED**

Machine-readable evidence is in `E2E_WORKFLOW_RESULTS.csv`,
`STRUCTURAL_SIZE_SECURITY_RESULTS.csv`, `SECURITY_FALSIFICATION_RESULTS.csv`,
and `results_canonical_v3/`.
