# Resource Leakage Report

## Status: RESOURCE_OPEN

Fixed endpoints and packets do not close coarse execution-resource leakage. In the 800-slot matched action workload,
resource-only action classification reached top-1 accuracy 0.468 (logistic regression) and 0.473 (random forest),
versus chance and permutation accuracy near 0.25. The all-feature random forest reached 0.577.

Measured fields:

- process CPU time;
- wall-clock time;
- Python peak traced allocation;
- working-set/RSS delta;
- client thread-count delta.

The shared LLM CPU proxy remained recognizable because the selected heavy primitive executes only for the real
workflow. This is the intended falsification pressure: running heavy work for every NOOP would violate the
`dummy_heavy_ops = 0` invariant.

Not measured: GPU utilization (no GPU telemetry available), hypervisor counters, cache traces, microarchitectural
events, or a TEE. Closing this channel would require a separately evaluated high-assurance profile such as
confidential execution plus resource shaping/confidential GPU. No such closure is claimed here.
