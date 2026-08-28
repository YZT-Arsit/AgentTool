# Real local LLM end-to-end report

## Result

`REAL_LOCAL_LLM_E2E = PASS` for one bounded OpenAI Agents SDK single-Tool workflow.
This is an external-validity case study, not the semantic oracle and not a model-quality evaluation.

The successful path was:

```text
native OpenAI Agent + FunctionTool
  -> IR-v2 compiler and strict single-Tool lowering
  -> trusted Control Kernel
  -> encrypted 1,024-byte frames
  -> opaque Cloud Slot Proxy
  -> CommonActionGateway V2
  -> local GPU model / local Tool providers
  -> encrypted result frames
  -> Tool result reinserted into the next model request
  -> final RETURN
```

## Model and runtime provenance

| Item | Exact value |
| --- | --- |
| Model | `Qwen/Qwen2.5-0.5B-Instruct` |
| Hugging Face revision | `7ae557604adf67be50417f59c2c2f167def9a775` |
| License | Apache-2.0 |
| Weight file SHA-256 | `fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe` |
| Parameters | 494,032,768 |
| Precision/device | BF16 on `cuda:0` |
| Weight memory allocated/reserved after load | 988,097,024 / 1,002,438,656 bytes |
| GPU | NVIDIA GeForce RTX 5090, 32,607 MiB |
| Driver | 580.76.05 |
| PyTorch / CUDA | 2.12.1+cu130 / 13.0 |
| Transformers | 4.57.6 |
| Accelerate | 1.12.0 |
| Python | 3.12.3 |

The exact public revision was queried through the Hugging Face API, and the files were downloaded from the configured Hugging Face mirror because the host's direct Hub connection stalled. The weight hash was recomputed locally after download. The model is deliberately small: the question is whether genuine GPU inference flows through the canonical boundary, not whether model quality is competitive.

The provider exposes an OpenAI-compatible `/v1/chat/completions` route and the Gateway's `/execute` ABI. The Gateway uses only `/execute`; the OpenAI-compatible route records provider-interface compatibility. Model inputs, raw outputs, normalization, and latency are private provider artifacts.

## Successful semantic projection

The successful attempt produced:

- two genuine GPU model invocations (532.157 ms and 307.872 ms generation time);
- one local read-only Tool call;
- exact structured arguments `{"topic":"synthetic-local"}`;
- stable private call ID `local-model-call` across call/result reinsertion;
- exact Tool result `READ_ONLY_TOOL:0` in the resumed model context;
- final sanitized result `completed: READ_ONLY_TOOL:0`;
- three real heavy operations, zero dummy heavy operations, zero external effects;
- 128 fixed frames in each direction over one persistent tunnel;
- 14,278.589 ms Gateway wall time, dominated by the public fixed schedule rather than GPU inference.

## Preserved negative attempts

Two failed integration attempts are retained rather than overwritten.

1. The first parser required an explicit `kind`; the model emitted `{"text":"completed:no-tool"}`. It was rejected.
2. After syntactic discriminator normalization, the model emitted a premature final answer instead of calling the mandatory Tool. The strict kernel did not reinterpret it as a Tool call; it entered repeated `NO_MATCH` control ticks and `returned=false`.

The successful third attempt changed only the generic provider prompt: when a Tool is present, it states that a Tool call is mandatory; when a Tool result is present, it requests a final response. A narrowly scoped adapter may infer a missing `kind` discriminator from an otherwise complete JSON shape, but it does not select the Tool, arguments, call ID, Tool result, or final text. Raw model output remains preserved.

## Limitations

- Only the strict native single-Tool stratum was exercised. Multi-Tool, Agent-as-Tool, and model-after-HANDOFF GPU workflows remain untested.
- The local provider and all Gateway roles ran on one user-owned Linux host. This demonstrates functional composition, not same-host isolation from malicious root.
- The real-model run is excluded from timing-privacy calibration and from privacy-overhead attribution.
- The 0.5B model required a strong generic schema prompt. This is valid flow evidence, but not evidence of robust autonomous Tool-use quality.

Raw successful evidence is under `results_canonical_v3/real_llm_e2e_qwen05b_v3/`; the two failed attempts are in the adjacent unversioned/v2 directories. Archive hashes are recorded in `SYSTEM_INTEGRATION_FINAL_REPORT_V2.md`.
