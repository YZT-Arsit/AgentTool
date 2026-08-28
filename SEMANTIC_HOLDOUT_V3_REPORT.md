# Semantic holdout V3 report

`SEMANTIC-HOLDOUT-V3-20260828` was frozen after harness development pretests and
then executed once. Its manifest digest is
`deabd8024f129ea7e1605bf7a964b632c8e1d74b07802924ed2a417e72a81330`.

| Framework | Cases | Passes | Errors |
| --- | ---: | ---: | ---: |
| OpenAI Agents SDK | 6 | 6 | 0 |
| Microsoft Agent Framework | 6 | 6 | 0 |
| **Total** | **12** | **12** | **0** |

Six cases are Tool-containing; two are handoffs; four are model-final. Every
native and compiled projection exactly matched its frozen projection and used
`AgentControlExecutorV2`. Cases came from four pinned official files excluded
from the V2 holdout source set.

This supports **12/12 semantic fidelity for these bounded strata**. It does not
replace IR-v1 48.39%, promote MIXED/UNPROVEN rows, or establish corpus-wide
fidelity. The V2 72/72 remains development regression only.
