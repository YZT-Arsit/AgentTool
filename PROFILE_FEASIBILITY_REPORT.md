# Profile feasibility report

## Scope

This audit combines two different evidence types without conflating them:

1. exact dynamic projections from the frozen 72-case IR-v2 fidelity set; and
2. static per-file behavior counts from the exact frozen 314-file corpus.

Static AST counts are not trajectories. They expose how much heavier the real
corpus can be, but they cannot establish sequential depth, payload size, or a
safe public horizon. No profile-fit percentage is inferred from them.

## Frozen dynamic distribution

| Metric | p50 | p90 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Model calls | 1 | 2 | 2 | 2 | 2 |
| Tool calls | 0 | 1 | 1 | 1 | 1 |
| Handoff depth | 0 | 1 | 1 | 1 | 1 |
| Control-update proxy | 2 | 6 | 6 | 6 | 6 |
| Tool argument bytes | 2 | 26 | 26 | 26 | 26 |
| Tool-result bytes | 2 | 20 | 20 | 20 | 20 |
| Next-model context bytes | 0 | 290 | 290 | 290 | 290 |
| Final-result bytes | 13 | 16 | 16 | 16 | 16 |

The four capsules used by the completed Linux workflows are all 1,024 bytes and
contain 1, 2, 4, and 4 control rows. This is a very small validated stratum, not
a corpus-size distribution.

## Candidate public profiles

The following diagnostic profiles use the dynamic control-update count as the
horizon proxy, fixed 1,024-byte bidirectional frames, and 40 ms per public step.
They exclude PIR, process startup, inter-session gaps, and real provider/model
latency.

| Profile | Fit | Overflow | Mean cover fraction | Bidirectional bytes | Nominal duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| H=4, B=1024, Delta=40 ms | 75.0% | 25.0% | 25.0% | 8,192 | 160 ms |
| H=6, B=1024, Delta=40 ms | 100.0% | 0.0% | 41.7% | 12,288 | 240 ms |
| H=8, B=1024, Delta=40 ms | 100.0% | 0.0% | 56.25% | 16,384 | 320 ms |

H=6 fits the frozen 72 cases, but this does not justify adopting H=6 for the
corpus or for production.

## Corpus pressure

The static 314-file census has heavy tails. Per file, the p99/max counts are:

| Static behavior | p99 | max |
| --- | ---: | ---: |
| Agent constructors | 48 | 102 |
| Tool instances | 50 | 255 |
| Conditional edges | 19 | 36 |
| Loops | 5 | 11 |
| Fan-out/fan-in | 8 | 9 |
| State/memory references | 83 | 221 |
| HITL/resume references | 7 | 27 |
| Middleware references | 133 | 216 |

Many of these counts include tests, helpers, unsupported callbacks, and multiple
independent workflows in one file. They therefore cannot be summed into an
execution horizon. Their value is negative: the 72-case set is not sufficient
to claim realistic profile coverage.

## Missing measurements

- serialized IR-v2 capsule sizes across all corpus workloads;
- native trajectory traces for structured state, Agent-as-Tool, HITL, branch,
  and fork/join strata;
- sequential Tool and handoff depth across real corpus executions;
- real model-result and Tool-result distributions;
- overflow behavior under a fixed predeclared profile;
- provider/model latency distribution and public session policy cost.

## Conclusion

`PROFILE_FEASIBILITY` is **measured only for the frozen 72-case core and four
Linux capsules; corpus-wide feasibility remains OPEN**. The current data support
an H=6 functional test profile, not a general deployment profile. Full details
are in `PROFILE_FEASIBILITY_RESULTS.csv`.
