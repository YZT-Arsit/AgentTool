# Real-framework compilation audit

The audit instantiated native objects from the checked-out OpenAI Agents SDK
and Microsoft Agent Framework packages. It did not call a model. Overall
coverage was **81/85 = 95.3%** across 22 native Agent objects.

| Workload | Framework | Total | Compiled | Shared | Unsupported | Coverage | Capsule bytes | States | Transitions |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| language routing | OpenAI | 15 | 11 | 4 | 0 | 100.0% | 1,024 | 11 | 11 |
| customer service | OpenAI | 15 | 10 | 5 | 0 | 100.0% | 1,024 | 12 | 12 |
| Agent lifecycle | OpenAI | 9 | 5 | 3 | 1 | 88.9% | 1,024 | 6 | 6 |
| Agents as tools | OpenAI | 11 | 6 | 5 | 0 | 100.0% | 1,024 | 8 | 8 |
| dynamic instructions | OpenAI | 3 | 1 | 1 | 1 | 66.7% | 1,024 | 2 | 2 |
| simple tool | Microsoft | 4 | 2 | 2 | 0 | 100.0% | 1,024 | 3 | 3 |
| sequential workflow | Microsoft | 11 | 8 | 3 | 0 | 100.0% | 1,024 | 8 | 8 |
| conditional workflow | Microsoft | 7 | 4 | 2 | 1 | 85.7% | 1,024 | 4 | 4 |
| fan-out workflow | Microsoft | 10 | 6 | 3 | 1 | 90.0% | 1,024 | 6 | 6 |

Instructions, termination, unconditional handoffs, and sequential edges were
compiled. Model calls and Tool/Agent-as-Tool calls remained shared heavy
primitives. Arbitrary dynamic instruction callbacks, prompt-encoded conditions,
Python workflow predicates, and native parallel fan-out were `UNSUPPORTED`.
The denominator and every behavior-level classification are preserved in
`results_control_virtualization/behavior_classification.csv`.
