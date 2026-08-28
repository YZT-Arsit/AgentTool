# Resource Observer Boundary V3

## Feature ownership

| Feature | Visibility class | Base `O_agentcloud` evaluation? |
| --- | --- | --- |
| Cloud Slot Proxy CPU time/utilization | AGENT_CLOUD_VISIBLE | yes |
| Cloud Slot Proxy RSS/allocation | AGENT_CLOUD_VISIBLE | yes |
| Cloud Slot Proxy thread/process count | AGENT_CLOUD_VISIBLE | yes |
| Cloud Slot Proxy context switches | AGENT_CLOUD_VISIBLE | yes |
| U-to-Gateway socket bytes/count/timing | AGENT_CLOUD_VISIBLE | yes |
| Public profile/session/slot identifiers | AGENT_CLOUD_VISIBLE | yes |
| Gateway Pacer CPU/RSS/queue state | TRUSTED_GATEWAY_ONLY | no |
| Gateway Worker CPU/RSS/thread activity | TRUSTED_GATEWAY_ONLY | no |
| Private request/result ring occupancy | TRUSTED_GATEWAY_ONLY | no |
| EffectGate/provider adapter state | TRUSTED_GATEWAY_ONLY | no |
| Local provider CPU/RSS/service timing | REMOTE_PROVIDER_ONLY | no |
| Model GPU/VRAM/CUDA kernels | REMOTE_PROVIDER_ONLY | no |
| Tool-side process/filesystem activity | REMOTE_PROVIDER_ONLY | no |
| Privacy Kernel CPU/RSS/PIR client state | TRUSTED_KERNEL_ONLY | no |

The canonical Agent-Cloud resource observer is the untrusted U process and its
public tunnel only. Prior action-type resource experiments that included
provider or Gateway-private measurements do not instantiate this observer.

## Phase-6 measurement status

`RESOURCE_PRIVACY = OPEN`. A full canonical live path is a prerequisite. Since
Windows Application Control blocked the Pacer process, no U workload/resource
trace exists and no classifier was run. Adding a TEE, resource shaper, or proxy
cover workload merely to obtain a PASS is outside this task.

## Predeclared future features

If the process policy is resolved on an authorized host, collect per public
epoch: U process user/system CPU, peak and sampled RSS, voluntary/involuntary
context switches, thread count, socket bytes, fixed-frame counts, and public
send/receive timestamps. Ground truth remains a separate trusted file. Group by
semantic task/session and report effect size, bootstrap interval, and
permutation control; `p > 0.05` alone is not privacy evidence.

