# V12.1 final system gate

Status: **FAIL — stopped before any V12 holdout universe, seed, selection, authorization, or execution.**

The targeted reliability repair succeeded on the frozen Linux development host: B5 count25 100/100 and count50 100/100, with exact lifecycle IDs, 356/356 rounds, and zero safety counters. Linux Go packages also passed. Existing SimplePIR closure, resource lifecycle, 500-unit stress, 5/5 rehearsals, and 22/22 security negatives remain append-only PASS evidence.

The mandatory full serial Python gate did not become completely green. On the evidence-complete Windows workspace, the explicit V12-reachable scope produced 297 passed, two `SESSION_BUDGET_EXHAUSTED_WITH_PENDING_RESULT` failures, two pre-existing environment skips, and one transparently deselected superseded V10 static test. Therefore the default suite and post-change profile requalification were not run. Existing pre-repair requalification is preserved but is not reused as post-change qualification.

The Linux evidence-host full collection was also run serially as an environment audit: 157 passed, 14 failed, and nine pre-existing skips. Those 14 failures were caused by historical artifact/host-layout dependencies absent from that checkout, so they are not used to conceal or replace the two execution-reachable Windows failures.

Per the fail-closed rule, `V12_MASTER_EXCLUSION_SET.json`, candidate universes, seeds, selected manifests, execution order/plan, environment/artifact freezes, authorization, and `results_v12_confirmatory` were not created.
