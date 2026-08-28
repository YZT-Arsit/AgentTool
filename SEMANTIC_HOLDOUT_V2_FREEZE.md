# IR-v2 Semantic Holdout Freeze

The 72/72 IR-v2 result is now classified permanently as a **development
regression result**. Those cases informed the Tool-loop repair and are not an
untouched semantic holdout.

`SEMANTIC_HOLDOUT_V2_FREEZE.json` defines 20 new deterministic,
source-traceable cases selected from pinned official files not used by the
72-case repair set. Fourteen cases are Tool-containing, including bounded
Agent-as-Tool call/return. Both pinned frameworks are represented.

The manifest freezes before execution:

- case IDs and framework/source commit;
- exact source path, line range, and file SHA-256;
- public task;
- deterministic model/Tool/child-Agent responses;
- exact expected semantic projection;
- pass criteria and no-tuning rules.

The generator refuses to overwrite an existing freeze. Its companion SHA-256
file authenticates the frozen JSON. Execution code and result artifacts must be
separate and must verify the manifest digest before running.
