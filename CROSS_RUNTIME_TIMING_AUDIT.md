# Cross-runtime timing audit

Cross-runtime transfer is diagnostic only. Training on Microsoft and testing on OpenAI produced receiver-arrival AUC 0.519 (LR) / 0.558 (RF) and all-observer AUC 0.530 / 0.539. Reversing direction produced receiver-arrival AUC 0.491 / 0.508 and all-observer AUC 0.540 / 0.496.

These values do not show a strong portable classifier. They also do not negate the within-runtime state-family leaks. The residual signal appears partly runtime-specific, while the shared failure mode is imperfect control of actual deadline/transport timing under load.
