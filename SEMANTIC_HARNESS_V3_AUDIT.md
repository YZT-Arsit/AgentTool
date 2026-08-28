# Semantic harness V3 audit

The V2 holdout remains 8 valid passes plus 12 `HARNESS_INVALID`; it was not
rerun. V3 uses a reusable harness that separately constructs pinned native
framework Agent objects, validates their Tool/handoff surfaces, derives a
native deterministic semantic projection, compiles the same objects, executes
the bounded IR runtime, and compares both projections to one frozen expected
projection.

Before selecting holdout cases, two development-only fixtures passed:

- OpenAI model/Tool/model with an explicit one-argument Tool schema;
- OpenAI handoff with generic root-actor alias resolution.

These pretests directly cover the prior Tool-schema and actor-alias harness
defects. The harness supports model-final, Tool loop, handoff, and Agent-as-Tool
forms; only the first three were selected for V3 holdout because the available
Agent-as-Tool examples had already informed earlier development.

Limit: the deterministic native projection is an offline semantic oracle over
actual native object structure and a frozen local transcript. It does not run a
network model or exercise every native framework middleware/session behavior.
