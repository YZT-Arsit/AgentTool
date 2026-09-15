# Final comprehensive evaluation

FINAL SYSTEM:
    real APSI + real SimplePIR
    100K Agent artifact store
    TEE Agent Loader
    R_A = 4
    Delta_A = 350 ms
    fixed one-slot pipeline
    frozen Gateway profile

UTILITY:
    semantic success = 240/240
    profile conformance = 280/280

ACCESS PRIVACY:
    same-Agent AUC = 0.514
    cross-session AUC = 0.468 / 0.521
    sequence-ordering accuracy = 0.252
    recurrence AUC = 0.478
    rare-Agent AUC = 0.558
    return-pattern AUC = 0.373 (orientation-invariant diagnostic 0.627)

STRUCTURAL TRAJECTORY PRIVACY:
    exact permitted-projection equality = PASS
    classifier accuracy = 0.212

TIMING:
    strongest final Gateway AUC = 0.645
    exact residual setting = TOOL_VS_AGENT_AS_TOOL / Microsoft Agent Framework
    deployed/unprovisioned/idle timing accuracy = 0.663
    TIMING_PRIVACY = NOT_ESTABLISHED

SCALE:
    100K schema-valid provisioned-Agent artifacts = PASS

OVERHEAD:
    9.903 MiB/public profile
    11.318 MiB/measured execution mean
    retrieval p50/p95 = 771.729/7466.234 ms
    task p50/p95 = 5002.551/14880.534 ms

DUMMY HEAVY OPS:
    Agent = 0
    LLM = 0
    Tool = 0

## Final system

- Real Microsoft APSI + real SimplePIR over 100K authenticated provisioned-Agent artifacts.
- Trusted Agent Loader; no remote Agent service execution.
- `R_A=4`, `Delta_A=350 ms`, 1,425 ms public Agent-access horizon, fixed one-slot pipeline.
- Frozen 521-cell Gateway profile.

## Utility

- Semantic success: **240/240** non-idle executions.
- Profile conformance: **280/280** sessions.
- Retrieval latency over 480 successful retrievals: **771.729 ms p50 / 7466.234 ms p95**.
- Semantic task latency over successful non-idle executions: **5002.551 ms p50 / 14880.534 ms p95**.
- Overflow: **0**; silent loss: **0**.
- Profile-capacity failures: **0**; retrieval failures: **0**; Agent Loader failures: **0**.

## Access privacy

- Same-Agent linking (primary `ALL_ALLOWED` view): AUC **0.514**, 95% CI [0.449, 0.579], p=0.329.
- Cross-session same-slot linking: AUC **0.468**, 95% CI [0.415, 0.520], p=0.8823.
- Cross-session cross-slot linking: AUC **0.521**, 95% CI [0.470, 0.573], p=0.2153.
- Four-class ordering/recurrence accuracy: **0.252** (chance 0.25), macro-F1 0.247, 95% CI [0.203, 0.302], p=0.4742.
- Strongest binary Agent-access timing-only result: **SAME_AGENT_WITHIN_SESSION**, train-oriented AUC **0.562**, orientation-invariant diagnostic 0.562, 95% CI [0.495, 0.626], p=0.0329.
- Capture integrity: **11814/16000** APSI observations had exact payload-byte capture; **1621** sessions were eligible for `CONTENT_CRYPTOGRAPHIC`, `TIMING`, and `ALL_ALLOWED`. Structural views retain all sessions.
- Observer-representation boundary: exact-byte-count APSI captures are represented by frozen stream digests, byte histograms, and fixed public offsets. The SimplePIR adapter retained its actual query digest and public sizes/timing, but not the raw answer payload. Accordingly these are direct attacks on the recorded joint-channel representation, not an exhaustive empirical claim over every raw SimplePIR answer byte.

## Structural trajectory privacy

- Full-session permitted structural projection: **PASS**, with Agent-access projection SHA-256 `091b83a141ca2d24c8417ca980bf9fbd2080a20436b8a68fe422e802fcbd4912` across 8 private patterns.
- Final composed structural attack: accuracy **0.212**, macro-F1 0.088, 95% CI [0.150, 0.275] against 0.25 chance.
- This result composes the historical matched action records with constant final Agent-access and unchanged Gateway structural fields; it is not mislabeled as a fresh integrated 800-session campaign.

## Timing

- Strongest final Gateway result: **TOOL_VS_AGENT_AS_TOOL / Microsoft Agent Framework**, AUC **0.645**, 95% CI [0.465, 0.818], p=0.06119.
- Agent-access deployed/unprovisioned/idle timing-only classification: accuracy **0.663**, 95% CI [0.610, 0.717], p=9.999e-05.
- **TIMING_PRIVACY = NOT_ESTABLISHED.** No timing result is omitted or averaged away.
- A preserved preflight manifest mismatch aborted before any timing runtime session; it contributes zero observations and is not counted as a retry or failed sample.

## Scale

The scale sweep uses 1K, 10K, 50K and 100K schema-valid artifacts with persistent real cryptographic services and 30 measured queries per point. `FINAL_SCALE_RESULTS.csv` reports preprocessing/storage, online p50/p95 and exact wire bytes. The corpus is not described as 100K independently collected real-world Agents.

## Overhead

- Agent-access channel: **9,405,600 B (8.970 MiB) per public profile**.
- Gateway channel: **978,959 B (0.934 MiB) per public profile**.
- Total: **10,384,559 B (9.903 MiB) per public profile**.
- The 280 measured executions used **320** public profiles; mean measured traffic was **11,868,067.429 B (11.318 MiB) per execution**. Unprovisioned nested workloads required a second bounded public profile rather than silently extending one profile.
- The channels can overlap in wall-clock time; their byte counts are additive, their horizons are not.

## Dummy heavy operations

- Dummy Agent executions: **0**.
- Dummy LLM executions: **0**.
- Dummy Tool executions: **0**.

The final claim classifications are in `FINAL_CLAIM_MATRIX.md`; every candidate manuscript number and its evidence boundary is in `FINAL_PAPER_NUMBER_MAP.md`.
