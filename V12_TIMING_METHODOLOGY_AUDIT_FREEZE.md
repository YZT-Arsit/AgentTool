# V12 Timing Methodology Audit Freeze

- Base commit: `1cf12990fdfc005f59ee6d31943c40db53c5408b`
- Scope: local synthetic timing-privacy methodology only
- Timing workload sessions executed in this closure: **0**
- Existing 16-row matrix primary nonlinear validity: **FAIL**
- Historical disposition: **AUXILIARY_FACTORIAL_SCREENING**

The ten label columns are parity functions of four row bits. The binary design
matrix has GF(2) rank four; for example, `T1 XOR T2 = T3` and
`T1 XOR T4 = T5`. Pairwise balance and orthogonality therefore do not remove
higher-order aliases available to nonlinear classifiers.

## Protected vector-length audit

**PROTECTED_VECTOR_LENGTH_CONSTANT = YES** within one public profile and
observer. The protected Relay transcript contains exactly public `R` cells in
one session. The protected Registry transcript contains exactly public
`Q = 6000 / 60 = 100` queries. Raw widths are derived from public `R` and `Q`
and must match exactly; private-length padding is rejected. Therefore the
previously suspected raw-vector-width/zero-padding leak is not present in the
protected fixed-transcript design. This does not change the matrix-aliasing
verdict.

Relay `R` is profile-specific (`506`, `279`, or `233` for the existing
development candidates) and is constant across protected classes within that
profile. No profile or Delta is selected by this freeze.

## Registry timestamp audit

`pir_integration/simplepir_bridge/main.go` records `answer_ready_ns` immediately
after server answer computation and before trace flushing and JSON response
encoding/writing. It is internal computation completion, not an
application-send boundary timestamp. TIMING_ONLY_VIEW excludes it. The
methodology accepts a future `response_send_ns` only when application-boundary
instrumentation supplies it; this closure does not change the PIR runtime.

The Relay's current `response_observed_ns` is likewise recorded before
`WriteHeader`/`Write`, with event-recording work in between. It is excluded
from TIMING_ONLY_VIEW. Relay response sequences are admitted only from an
explicit application-boundary `response_send_ns`.

## Primary design

Primary tasks use independently randomized matched pairs per task and
framework. T1 is `NOT_FEASIBLE` under the frozen cache semantics because the
current harness cannot vary reusable-versus-re-resolution cache state while
holding semantic Agent identity and all other protected factors fixed. T7, T8,
and T10 are explicitly composite estimands. Historical T1 remains auxiliary.

Decisive development inference uses a deterministic 60/40 split of complete
matched blocks. Models and preprocessing fit on TRAIN only. Four frozen
classifier prediction vectors are evaluated on independent EVAL blocks. Each
bootstrap replicate resamples complete EVAL pairs and takes the maximum of the
four AUCs. Models are not refit inside the EVAL bootstrap.

Approximate chance-AUC 95% half-widths for planning a single fixed AUC are:

| EVAL blocks | Sessions | Approx. half-width |
|---:|---:|---:|
| 100 | 200 | 0.0802 |
| 150 | 300 | 0.0654 |
| 200 | 400 | 0.0567 |
| 300 | 600 | 0.0462 |
| 400 | 800 | 0.0400 |

The family-maximum interval may be wider. Bootstrap replicate count never
substitutes for independent blocks.
