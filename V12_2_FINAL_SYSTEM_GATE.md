# V12.2 final target-platform system gate

Status: **FAIL — stopped before fresh holdout construction.**

The Linux equivalents of the two Windows durability-sensitive failures passed 200/200. The predeclared Class-A serial suite then executed all 117 frozen nodes exactly once and produced 105 passes, 12 failures, and zero skips. Eleven failures were caused by the target checkout lacking the frozen V10 manifest prerequisites read by `test_v10_1_executor.py`; the twelfth found the pre-existing historical `results_v11b_confirmatory` root in the V11B driver guard test. Because all twelve nodes were classified Class A before execution, they are not reclassified, retried, or repaired after outcome observation.

The default Class-A suite, V12.2 Go gate, targeted B5 50+50, profile requalification, affected B4/B5 performance, and affected B4/B5 privacy-matrix execution were therefore not run. Historical evidence remains labeled separately and is not substituted for these missing post-repair gates.

No V12 execution harness freeze, master exclusion, universe, seed, selected manifest, execution order, plan, authorization, or confirmatory result root was created. Selected V12 execution count remains zero.
