# Timing and size attack report

The observer sees ordered events, operation classes, ORAM physical paths, actual frame byte counts, actual inter-event timing, total duration, idle gaps, and public commit. Ground truth is stored in separate CSV files.

Three repetitions of 40 paired tasks were evaluated per runtime, state family, and M0--M3 variant. Task IDs were group-split 70/30. Logistic regression and random forest were run for seven feature sets with three split seeds and shuffled-label controls.

The aggregate shuffled-label AUC was 0.5004 (M3: 0.5010), confirming that the positive live timing result is not a broken chance baseline.

| Runtime/family | M0 all | M1 all | M2 structural | M2 all | M3 structural | M3 size | M3 timing | M3 all |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Agent Framework / authorization | 1.000 | 1.000 | 0.502 | 1.000 | 0.502 | 0.500 | 0.631 | 0.603 |
| Agent Framework / provenance | 1.000 | 1.000 | 0.502 | 1.000 | 0.502 | 0.500 | 0.595 | 0.619 |
| OpenAI SDK / authorization | 1.000 | 1.000 | 0.535 | 1.000 | 0.535 | 0.500 | 0.558 | 0.555 |
| OpenAI SDK / provenance | 1.000 | 1.000 | 0.535 | 1.000 | 0.535 | 0.500 | 0.566 | 0.617 |

M3 aggregate AUC: structural 0.518, size 0.500, timing 0.588, all features 0.598. Fixed size is therefore effective; public bucketing is not, because native response sizes cross different buckets. P90/P95 have more deadline misses. P99 is the best evaluated setting but still does not reduce timing inference to permutation.

The negative result is preserved. High-resolution Python/Windows scheduling and occasional slot overruns remain a privacy channel; success likely requires a stronger transport/runtime scheduler or a coarser explicitly declared timing observer.

Mean wire bytes per episode were 125,369/237,568/127,744 for Agent Framework and 138,345/237,568/150,272 for the OpenAI SDK under none/fixed/bucketed shaping. Bucketing is cheaper but leaks the native-response bucket, so fixed size is the selected size mode.
