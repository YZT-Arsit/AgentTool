# V15A historical evidence status

This audit does not modify the manuscript. Status is relative to the integrated
paper system after adding real 100K APSI and loadable 100K artifact records.

| Manuscript result | Status | Mechanical reason |
|---|---|---|
| 100K deployed-Agent scale | `STILL_DIRECTLY_VALID` | V14 constructed 100,000 schema-valid, authenticated, loadable artifact records plus a real 100K APSI SenderDB and real 100K SimplePIR database. The corpus is synthetic scale data, not 100K independently sourced real-world Agents. |
| 16K same-Agent linking | `MUST_RERUN` | The old workload used a different 1K capsule-template registry, no APSI, and no loadable-artifact session scheduler. It is not a result for the V14/V15 path. |
| Cross-session linking | `MUST_RERUN` | The old access transcript does not include the real APSI+PIR schedule and uses stale record semantics. |
| Structural four-class accuracy | `MECHANISM_VALID_BUT_DATASET_STALE` | The result remains evidence for the frozen V4R8 Gateway-normalization mechanism, but it does not cover an integrated session with the new 2,351,400-byte Agent-access slots. |
| Timing AUC | `STALE_RESULT` | The negative conclusion `TIMING_PRIVACY = NOT_ESTABLISHED` remains preserved; its numerical AUCs do not measure the new real APSI+PIR layer. They must not be averaged with or substituted for future integrated results. |
| 240 task success | `IMPLEMENTATION_PATH_STALE` | Historical runs resolved descriptor-only rows and did not retrieve, authenticate, load, and execute `ProvisionedAgentArtifactV1`. |
| 240 profile conformance | `IMPLEMENTATION_PATH_STALE` | Gateway conformance remains component evidence, but the run did not execute real APSI+PIR at every Agent-access opportunity. |
| 0.41--1.89 s latency | `MUST_RERUN` | It excludes the real 100K APSI path and therefore is not final-system latency. |
| 1.755 MiB/session | `MUST_REMOVE` | It excludes APSI. Under the unaffordable 100-slot candidate, measured protocol sizes project 236,118,959 public bytes/session (about 225.18 MiB), including the frozen Gateway channel. |

No privacy attack, linking workload, sequence classifier, timing AUC, or
240-run utility campaign was executed in V15A.

