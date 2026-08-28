# Canonical V3 Performance and Overhead

## Measurement boundary

The measurements keep six costs separate: native framework control, compiled
IR-v2 control, PIR preprocessing/online lookup, the public fixed transcript,
the live CommonActionGateway V2 run, and real local model inference. The model
is an external heavy primitive; its inference time is not counted as privacy
overhead.

## Control-plane microbenchmark

On the Linux host, 50 source-traceable OpenAI `model -> Tool -> model`
executions produced:

| Path | Mean | p50 | p95 | Semantics |
| --- | ---: | ---: | ---: | --- |
| Native OpenAI Agents SDK | 3.479 ms | 3.452 ms | 3.869 ms | PASS |
| IR-v2 compile + trusted interpreter | 0.867 ms | 0.863 ms | 0.881 ms | PASS |

The compiled measurement includes compiling the one-Agent workload in every
sample. It is a deterministic control-plane microbenchmark, not an LLM latency
benchmark and not a claim that the compiled implementation is generally faster
than every native runtime.

## Real PIR

The pinned official SimplePIR integration performed real preprocessing and
correct recovery of 1,024-byte capsule records.

| Logical records | Preprocessing | Online query + answer + recovery | Upload | Download | Persistent client state |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 40.907 ms | 0.800 ms | 2,020 B | 6,592 B | 8.80 MB |
| 10,000 | 552.913 ms | 3.743 ms | 10,024 B | 13,184 B | 23.74 MB |
| 100,000 | 23,506.850 ms | 23.640 ms | 36,388 B | 37,180 B | 75.31 MB |

The 100,000-row logical database uses 100,001 physical rows, so physical
storage includes one 1,024-byte padding record. Peak allocation for that run
was 1.444 GB. Preprocessing is reported separately and must not be hidden in an
online-only number.

## Fixed transcript and Gateway

The deterministic canonical profile exposes 18 request plus 18 response frames
of 1,024 bytes: 36,864 public bytes and a computed public schedule of 1.370 s.
For a three-heavy-operation Tool workflow, 30 of those frames carry cover at
the application protocol level; cover causes no provider call.

The real-model case used a deliberately wider profile: 128 frames in each
direction, 262,144 public bytes, and a computed schedule of 13.600 s. Measured
Gateway wall time was 14.279 s. The profile carried three real heavy operations
and 250 cover frames with zero dummy heavy operations. This demonstrates the
cost shape of fixed scheduling; it is not a timing-privacy result because the
host failed the timing reference-platform gate.

## Real model

The two Qwen2.5-0.5B-Instruct generations averaged 420.014 ms per call and used
approximately 1.002 GB of reserved CUDA memory. That cost belongs to the real
workload. The privacy mechanism did not execute duplicate or dummy model calls.

## Missing measurements and interpretation

- General CPU utilization and process RSS were not captured robustly on the
  minimized container and are `NOT_MEASURED`; no value is inferred.
- Gateway process startup is not isolated from live wall time.
- The Linux allocation has a 25-CPU cgroup quota, no `SCHED_FIFO`, and no
  dedicated-core proof. Its latency values are functional/performance evidence,
  not confirmatory timing-privacy evidence.
- PIR client/server roles are algorithmically separated by the official bridge,
  but the current bridge runs them in one local process for the canonical test.

Machine-readable values are in `PERFORMANCE_RESULTS.csv`.
