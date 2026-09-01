# V12 null-precision calibration

This planning run generated artificial independent numeric score arrays only. It read no project trace or observer projection. Each of 250 outer null trials per candidate used 10,000 complete matched-EVAL-block bootstrap resamples and the 95th percentile one-sided UCB.

| EVAL blocks | Median UCB95 | 90th percentile | 95th percentile | P(UCB95 <= 0.55) | Criterion |
|---:|---:|---:|---:|---:|---|
| 150 | 0.552801 | 0.599131 | 0.613613 | 0.468 | FAIL |
| 200 | 0.547701 | 0.581476 | 0.592814 | 0.536 | FAIL |
| 250 | 0.543280 | 0.576370 | 0.581437 | 0.604 | FAIL |
| 300 | 0.538223 | 0.569032 | 0.577425 | 0.696 | FAIL |
| 400 | 0.534263 | 0.561251 | 0.566511 | 0.776 | FAIL |
| 500 | 0.531906 | 0.554124 | 0.560549 | 0.864 | FAIL |
| 600 | 0.526952 | 0.547981 | 0.554653 | 0.908 | PASS |
| 750 | 0.524925 | 0.546305 | 0.551176 | 0.944 | PASS |
| 1000 | 0.520435 | 0.537652 | 0.542621 | 0.988 | PASS |

The frozen rule selects the smallest candidate with probability at least 0.90. Therefore `EVAL_BLOCKS=600`, `TRAIN_BLOCKS=900`, and `TOTAL_BLOCKS_PER_COORDINATE=1500`.

The derived full cost is 3,000 sessions per workload/framework coordinate. Ten comparisons in each of two frameworks produce 60,000 sessions per profile. At the common 6,000 ms public-schedule floor, that is 100 serial hours per profile and, if all P10/P20/P25 candidates are reached, 180,000 sessions and 300 serial hours (12.5 days). This lower bound excludes startup, analysis, and queueing.
