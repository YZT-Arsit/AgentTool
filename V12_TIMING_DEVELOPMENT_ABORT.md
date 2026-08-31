# V12 timing development abort

The phase stopped before any attack-dataset session or timing-confirmatory session. The first frozen development identity, `DEV-TD-CAPACITY50-P10-PIR60`, was invoked once and was not retried.

## Classification

This is `ABORTED_HARNESS_INTEGRITY_FAILURE_BEFORE_ATTACK_SESSIONS`, not a valid 10 ms candidate-profile result. The local frozen `v11_online/session.py` SHA-256 was `a82c90cf33331c9e15936f159f5974b4933941f6f162ca58d5a425c78df5a052`, while the execution host used stale bytes with SHA-256 `2d6059549423e7c6c9879d576041e9d8606333fd0a0ca5fb552b1d786e8e8f13`.

The mismatch was behaviorally visible: the frozen implementation starts PIR ordinal 0 after a public 25 ms initial lead, but the observed private PIR schedule recorded ordinal 0 at 0 ns. The campaign launcher did not verify the transitive runtime hashes before invoking the capacity identity. That preflight omission is itself a harness defect.

## Preserved observation

The session still emitted a complete 356-cell transcript with fixed outer sizes and no liveness failure. It admitted, invoked, and returned exactly four operations. The fixed PIR transcript contained 50 real SimplePIR protocol executions, but only ordinals 42, 44, 46, and 48 carried real resolutions; 46 carried authenticated dummy resolution. The first framework intent appeared 2.734094438 seconds after `SESSION_T0`, after most fixed opportunities had elapsed.

The lifecycle contained 50 `ACTION_INTENT_SUBMITTED` entries but only four `DYNAMIC_PIR_DESCRIPTOR_RECOVERED` and four `FRAMEWORK_RESULT_DELIVERED` entries. The first missing framework execution was `opTDC1004`.

## Separate design finding

Even apart from the deployment mismatch, the raw trace exposes a capacity issue requiring independent redesign: after causal execution began, real resolutions occupied alternating PIR opportunities because each later action was created after the previous framework-visible result. Exactly `M` fixed PIR opportunities therefore do not mechanically guarantee `M` causal real resolutions. This finding is not used to reinterpret the integrity-invalid execution as a 10 ms candidate failure.

No source repair, rerun, substitute identity, candidate extension, attack analysis, timing confirmation, final V12 holdout construction, or selected final V12 execution followed this failure.

## Claim boundary

- `TIMING_PRIVACY = INCONCLUSIVE`
- `TIMING_GO = NO`
- `PACKET_LEVEL_TIMING = OPEN / NOT TESTED`
- `HARDWARE_TEE = NOT_TESTED`
- final V12 candidate universe absent
- final V12 seed absent
- selected final V12 executions: 0

The immutable raw evidence remains at `/root/autodl-tmp/results_v12_timing_dev_p10`; its hashes are bound in `V12_TIMING_DEVELOPMENT_ABORT.json`.
