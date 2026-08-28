# Frozen IR-v1 unsupported-behavior Pareto

The complete analysis is in `IR_V1_UNSUPPORTED_DECOMPOSITION.md`; the compatibility CSV requested for the canonical integration phase is `UNSUPPORTED_BEHAVIOR_PARETO.csv`.

All **3,812** historical `UNSUPPORTED` instances remain unsupported in IR-v1.

| Rank | Family | Instances | Files | OpenAI | Microsoft | Structured/bounded | Arbitrary callback/runtime | Mixed/unproven | Extractor artifact |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | state_memory | 1,589 | 101 | 325 | 1,264 | 0 | 0 | 1,589 | 0 |
| 2 | middleware | 932 | 14 | 0 | 932 | 0 | 932 | 0 | 0 |
| 3 | conditional_edge | 738 | 195 | 530 | 208 | 450 | 142 | 0 | 146 |
| 4 | loop | 165 | 75 | 101 | 64 | 6 | 0 | 159 | 0 |
| 5 | fanout_fanin | 156 | 64 | 82 | 74 | 0 | 2 | 2 | 152 |
| 6 | hitl_resume | 143 | 39 | 97 | 46 | 63 | 0 | 80 | 0 |
| 7 | agents_as_tools | 61 | 12 | 25 | 36 | 0 | 0 | 61 | 0 |
| 8 | dynamic_instructions | 18 | 16 | 18 | 0 | 0 | 5 | 13 | 0 |
| 9 | guardrail | 7 | 3 | 7 | 0 | 0 | 7 | 0 | 0 |
| 10 | conditional_handoff_callback | 3 | 3 | 3 | 0 | 0 | 3 | 0 | 0 |

This is a decomposition, not an IR-v2 coverage forecast. Source-traceable examples, framework file counts, feasibility boundaries, and required restricted primitives are preserved in `IR_V1_UNSUPPORTED_EXAMPLES.csv`, `IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv`, and `IR_V1_UNSUPPORTED_DECOMPOSITION.md`.
