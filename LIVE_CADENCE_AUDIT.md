# Live cadence audit

All cadence selection and repair decisions used the 40-task corpus. Following the Stage-13 scope update, every result below is development evidence, not an untouched final test.

## Calibration-derived cadences

| Runtime | P90 | P95 | P99 | Selected P99+1ms |
|---|---:|---:|---:|---:|
| Microsoft Agent Framework | 1.9140 ms | 2.0118 ms | 3.2921 ms | 4.2921 ms |
| OpenAI Agents SDK | 3.6307 ms | 3.7004 ms | 5.2975 ms | 6.2975 ms |

## Development operating points

| Runtime | Cadence | Overflow | Deadline misses | Mean latency |
|---|---|---:|---:|---:|
| Microsoft | P90 | 54.17% | 1.25% | 9.69 ms |
| Microsoft | P95 | 48.96% | 0.83% | 10.14 ms |
| Microsoft | P99 | 13.54% | 2.29% | 16.67 ms |
| Microsoft | P99+1ms | 0% | 1.67% | 21.56 ms |
| OpenAI | P90 | 21.88% | 2.71% | 18.30 ms |
| OpenAI | P95 | 15.63% | 1.67% | 18.59 ms |
| OpenAI | P99 | 0% | 0.63% | 26.58 ms |
| OpenAI | P99+1ms | 0% | 3.75% | 31.64 ms |

The selected P99+1ms cadence was predeclared before each measured final phase. In the latest repeated development run it still produced one Microsoft fail-closed overflow among 192 M3 episodes (0.52%) and no OpenAI overflow.

## Final repeated-run overhead

| Runtime | M2 latency | M3 latency | Ratio | M3 dummy fraction | M3 deadline misses |
|---|---:|---:|---:|---:|---:|
| Microsoft | 10.24 ms | 21.57 ms | 2.11x | 50.10% | 1.25% |
| OpenAI | 13.47 ms | 31.66 ms | 2.35x | 50.00% | 1.46% |

State-conditioned deadline-slip tails differ materially. For example, Microsoft authorization branch 0 had mean slip 0.45 us and max 3.8 us, while branch 1 had mean 118.37 us and max 10.33 ms. Therefore secret-dependent deadline slip is present.
