FINAL TIMING DECISION: TIMING_CONDITIONAL_GO

PIR TIMING: OPEN  
MULTI-ROUND TIMING: OPEN  
ACTION-TYPE TIMING: OPEN  
TOOL TIMING: OPEN  
DUMMY HEAVY OPS: 0  
RESOURCE PRIVACY: OPEN

# Timing Closure Final Report

## Executive result

The queue-and-pacer mechanism is operational at the socket boundary and materially reduces every previously strong
timing attack. It does **not** satisfy the full conservative acceptance gate. The correct result is
`TIMING_CONDITIONAL_GO`.

The mechanism succeeds causally: real downstream completion no longer calls or delays the cloud-visible response.
Both directions use fixed-size frames over one persistent `CommonActionGateway` connection, and the Gateway releases
only at public deadlines. Real SimplePIR queries—including randomized dummy-row queries—execute at every scheduled
PIR slot. Dummy heavy work remains zero.

The remaining blockers are empirical: a small significant combined PIR pairwise signal, non-converged Tool
frequency/transition estimates, action results below rather than cleanly at chance, rare large OS scheduling stalls,
and lack of packet-level capture.

## Before/after attacks

| Target | Before | Fresh frozen holdout after |
|---|---:|---:|
| PIR Agent frequency | LR AUC 0.738 | 0.361 LR / 0.319 RF |
| PIR repeated target | not closed | 0.527 LR (p=0.035) / 0.522 RF (p=0.095) |
| Tool repeated target | RF AUC 0.831 | 0.495 LR / 0.522 RF |
| Tool class | RF top-1 0.770 | 0.250 LR / 0.458 RF; chance 0.333 |
| Action type | RF top-1 0.544 | 0.125 LR / 0.125 RF; chance 0.250 |
| Cross-session PIR | prior structural control | 0.438 LR / 0.359 RF |

Below-chance values are reported as measured; they are not relabeled as perfect privacy. For action type they indicate
that the development mapping did not transfer, but they also fail the requested clean convergence-to-0.25 criterion.

## PIR fixed schedule

Each development and confirmatory split ran 66 episodes and 6,600 official SimplePIR operations:

- 100 scheduled queries per episode at 5 ms;
- 5,706 real-index queries;
- 894 randomized dummy queries against reserved rows 1000–1063;
- 6,600/6,600 exact recoveries;
- fresh query randomness for repeated indices;
- full preprocessing, answer, and recovery code for both real and dummy queries.

Agent frequency, rare-Agent, and real-vs-dummy occupancy classifiers show no significant advantage. Handoff-pattern
point estimates remain 0.556/0.639. Combined repeated-target timing produces LR AUC 0.527 with 95% bootstrap CI
0.501–0.553 and permutation p=0.035. Separately, request slip (AUC 0.523, p=0.065) and answer duration
(AUC 0.514, p=0.164) are not significant. `PIR_FIXED_SCHEDULE_TIMING` therefore remains OPEN.

## Common action channel and result queue

The implemented channel uses separate native cloud and Gateway processes and one persistent full-duplex loopback TCP
connection. Every slot sends one 1,024-byte frame each way to the same destination. Requests and responses have
independent native public clocks. Provider completion writes only to a private result queue; it does not send.

FAST, MEDIUM, SLOW, VERY_SLOW, and JITTERED providers performed real asynchronous work with measured means of about
16.9, 163.1, 794.4, 2,032.3, and 559.4 ms. Despite this range, the same 64-slot very-slow public schedule remained
visible. Mean completion-to-release delay was 22.4 ms (p95 64.3 ms) in that matrix.

## Tool timing

The strongest original failure—repeated target linkability—collapses to 0.495/0.522. Tool class is materially lower
but not closed: the random forest reaches top-1 0.458 with p=0.095. Tool frequency reaches AUC 0.639/0.667 and the
transition LR reaches 0.708, with wide intervals and no significant permutation evidence. Only six confirmatory
episodes per sequence class make these tests underpowered. They are preserved as OPEN rather than promoted to PASS.

All 3,000 requested Tool operations in the final long-sequence holdout completed exactly once. The 3,000 padding
slots invoked no concrete Tool and no heavy computation.

## Action-type timing

The frozen development-trained action classifiers obtain top-1 0.125/0.125 on 32 confirmatory action episodes,
below the 0.25 chance target. No individual timing ablation provides a significant above-chance attacker. Because
the result does not converge cleanly to chance and the holdout is small, status remains OPEN rather than PASS.

## Deadline behavior

Nominal request and response deadline gaps are exactly profile-fixed. Confirmatory p95 response slip is 0.99 ms for
single-action episodes and 1.61 ms for long Tool episodes. One 1,485.9 ms single-action stall and one 657.0 ms long
Tool stall occurred. These stalls are not significantly tied to the tested private classes, but demonstrate that a
general-purpose Windows scheduler does not provide a hard real-time guarantee.

## Fresh holdout discipline

Development seeds fixed the code, profiles, and feature definitions. An initial Gateway confirmation exposed a
functional bookkeeping bug: NOOPs were counted as queued results. Those artifacts are retained but invalidated.
The bug was fixed without changing public timing parameters, development was rerun, and entirely new seeds
`19001/19003` produced `confirmatory_final_*`. PIR confirmation was unaffected and remained untouched.

## Overhead

| Experiment | Public traffic | Mean / p95 latency | CPU | Heavy/dummy |
|---|---:|---:|---:|---:|
| Confirmatory single | 2.75 MB, 1,344 frames/direction total | 1,204 / 1,176 ms | cloud 1.39 s, Gateway 1.88 s | 40 / 0 |
| Confirmatory Tool sequences | 12.29 MB, 6,000 frames/direction total | 1,995 / 1,997 ms | cloud 5.95 s, Gateway 6.58 s | 3,000 / 0 |
| Confirmatory PIR | 57.71 MB | 517 / 530 ms per 100-slot episode | not separated | 0 / 0 |

The single-action mean exceeds p95 because of one 1.49 s scheduler stall. At PIR scale, client state is 8.93 MB and
peak Go allocation 44.35 MB. Fixed scheduling adds 894 dummy queries in the occupancy-control split. Complete
measurements are in `TIMING_OVERHEAD_RESULTS.csv`.

## Measurement and limitations

- Primary evidence uses actual socket send/receive timestamps on both sides of the persistent loopback connection.
- PIR evidence uses native server-call timestamps; it is not a packet trace.
- Packet capture was not performed because available `PktMon` capture is system-wide and could collect unrelated
  host traffic. No packet-level timing claim is made.
- Windows scheduling, loopback networking, small sequence-class sample sizes, and one machine limit generality.
- Resource privacy, provider collusion, global traffic analysis, arbitrary continuation epochs, and remote-provider
  resource telemetry are not closed.

## Decision

`TIMING_GO` is rejected because not every attack collapses cleanly to its control and packet-level PIR timing is not
validated. `TIMING_NO_GO` is also rejected: downstream completion is demonstrably decoupled, the large prior timing
signals are materially reduced, real/dummy PIR uses one real code path, the socket-boundary mechanism is independent
of Agent execution, and dummy heavy work is zero.

The defensible conclusion is:

> `TIMING_CONDITIONAL_GO`: preserve the native queued-release design, but do not claim full timing privacy until the
> small PIR pair signal and underpowered Tool sequence results are resolved on a real-time-capable host with a fresh,
> larger packet-level holdout.
