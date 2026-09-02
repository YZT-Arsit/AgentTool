# V12 Duplex V4R6 Reliability Continuation Closure

The infrastructure persistence gate passed. A harmless `nohup` worker completed after its controlling SSH shell disconnected, and the formal reliability worker was subsequently observed with PPID 1 from a new SSH connection.

The fresh synthetic public-path qualification passed **200/200** with zero retries, zero missing Relay slots, zero deadline misses, and maximum response-release slip `8229070` ns. The historical 28/28 remains separate supporting evidence and is not included in this denominator.

P10 functional requalification stopped at the first failure, as frozen. It executed 14/16 units: 13 passed and one failed. OpenAI passed 8/8. Microsoft passed its first 5 units; `DEV-DTVR-V4R6-P10-CONT-MS-CACHE_REUSE_30-002` failed only the `level_a_semantics` functional check while every recorded common-integrity check and all other recorded functional checks passed. It was not retried; the final two identities were not run.

Therefore `V4R6_SYNTHETIC_RELIABILITY = PASS`, `P10_V4R6_FUNCTIONAL = FAIL`, and `READY_FOR_DUPLEX_REPAIR_SMOKE = NO`. No protected classifier, AUC, P20, P25, or smoke execution occurred.
