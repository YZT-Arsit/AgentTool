# V12 causal-horizon capacity proof

This is a deterministic development-capacity argument, not a formal platform-jitter bound and not timing-privacy evidence. The immutable MDCC timings are used only to falsify candidates.

| H (ms) | admission slots | total cells | old-trace effective replay | PIR capacity | joint model | live eligible |
|---:|---:|---:|---:|---|---|---|
| 4500 | 450 | 506 | 50/50 | PASS | PASS | YES |
| 5000 | 500 | 556 | 50/50 | PASS | PASS | YES |
| 6000 | 600 | 656 | 50/50 | PASS | PASS | YES |

For each profile, `A=H/10`, `C=ceil(50/10)=5`, `M=50`, `T=1`, and `R=A+C+M+T`. Public request/response sizes remain 1079/800 bytes. The fixed Registry construction remains K=6, PIR60, epoch6000, Q=100; latest real descriptor arrival is `H-6*60-50-1` ms.

The causal model retains online generation: no future operation is made available before its predecessor's framework-visible result. It includes the historical same-Agent depth-50 arrival trace, K=6 transitions, Agent-as-Tool descriptor transitions, latest-legal result placement, measured framework intent delay, and no-burst public stalls of 35 ms, 100 ms, and repeated stalls.

The measured delays are not claimed as formal platform maxima. A live candidate must still pass both pinned frameworks and the complete frozen capacity matrix without retry or repair.
