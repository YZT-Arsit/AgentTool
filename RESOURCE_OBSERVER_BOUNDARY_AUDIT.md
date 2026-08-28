# Resource Observer-Boundary Audit

Resource privacy remains **OPEN** and was not repaired in this stage.

| Feature | Domain | Primary timing attacker? | Status |
|---|---|---:|---|
| AgentControlExecutor CPU/RSS/thread activity | `AGENT_CLOUD_VISIBLE` | Yes, but excluded from timing-only models | OPEN |
| PIR server CPU/memory and answer duration | `AGENT_CLOUD_VISIBLE` | Answer duration included | OPEN as resource channel |
| Native cloud pacer CPU/memory | `AGENT_CLOUD_VISIBLE` | Reported as overhead only | OPEN |
| Gateway CPU/RSS and private queue occupancy | `TRUSTED_GATEWAY_ONLY` | No | Outside frozen attacker |
| Remote LLM GPU/VRAM/kernel/queue | `REMOTE_PROVIDER_ONLY` | No | Outside frozen attacker |
| Tool-provider CPU/GPU telemetry | `REMOTE_PROVIDER_ONLY` | No | Outside frozen attacker |
| Local Word/process telemetry behind Gateway | `TRUSTED_GATEWAY_ONLY` | No | Outside frozen attacker |

The earlier local LLM CPU proxy was measured inside the Agent Cloud and remains valid evidence that local heavy
execution would leak. The frozen architecture instead routes heavy LLM/Tool work through the common trusted Gateway;
that administrative change does not close resource leakage from the cloud's own executor or PIR server.

No prior resource result was deleted. No TEE, confidential GPU, or resource shaper is claimed.
