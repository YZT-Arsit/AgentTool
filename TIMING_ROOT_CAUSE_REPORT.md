# Timing Root-Cause Report

## Reproduction before repair

The preserved raw traces and frozen attack code reproduce the prior failures:

| Attack | Dominant original field | Reproduced result |
|---|---|---:|
| PIR frequency M0 vs M2 | `SimplePIRServer.answer_ms` | LR AUC 0.738 |
| Tool repeated-target | immediate protected-call wall/RTT | RF AUC 0.831 |
| Tool class | immediate protected-call wall/RTT | RF top-1 0.770 (chance 0.333) |
| Action type | immediate slot wall time | RF top-1 0.544 (chance 0.250) |

Removing timing leaves the already-equal endpoint/count/size view at its analytical baseline. The old PIR trace did
not contain request-arrival or inter-request timestamps; its only measured timing signal was server answer duration.
The old Tool and action implementations returned as soon as the real downstream work completed, so round-trip time
was an almost direct completion-time proxy.

## Root causes

1. **Secret-triggered PIR/control progress.** Queries were executed in a tight application loop. Although every
   SimplePIR query was cryptographically fresh, server processing and temporal drift entered the episode feature.
2. **Completion-coupled Tool response.** `ToolBoundary.protected_call()` blocked until the concrete local/remote/cloud
   operation returned and immediately released the response.
3. **Completion-coupled action slot.** AGENT/LLM/TOOL/NOOP measurements ended when each action's real code path ended.
4. **No private result queue.** There was no boundary that separated downstream completion from cloud-visible release.

Absolute timestamp, inter-slot, request-send, Gateway-release, and completion-to-release fields were absent from the
old traces, so no stronger layer attribution is possible retroactively.

## Post-repair ablation

The new socket trace separates request schedule/slip, request ingress, Gateway response schedule/slip, response egress,
round-trip time, inter-request/inter-response gaps, session-relative time, and absolute phase.

- Action-type component attacks show no significant above-chance signal. The strongest component top-1 is 0.3125,
  but the frozen full attacker performs below chance rather than learning a transferable class mapping.
- Tool-class residuals concentrate in response slip/egress (top-1 up to 0.458) and their interaction. No single
  ablation is significant at 0.05 on the fresh holdout.
- PIR repeated-target ablation is weak separately: request-slip LR AUC 0.523 (p=0.065) and answer-duration LR AUC
  0.514 (p=0.164). Their combined attacker reaches AUC 0.527 with p=0.035.
- Two large state-independent OS/process stalls occurred: maximum response slips of 1,485.9 ms in the single-action
  run and 657.0 ms in the long Tool run, despite p95 slips of 0.99 and 1.61 ms. Labels were shuffled independently of
  execution order; no tested single layer ties these stalls reproducibly to a secret class.

## Earliest remaining divergence

The earliest measured residual is at the native scheduler/server boundary: scheduled-to-actual PIR invocation slip.
It is individually non-significant but contributes to the combined pairwise result. For the common action channel,
the first substantial variation is actual socket release/transport jitter, not downstream completion.

The evidence therefore supports the queue/pacer causal repair, but not a claim of complete timing closure.
