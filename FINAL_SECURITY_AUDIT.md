# Final security audit

## Declared view and leakage class

Public: initial task, tool/effect type, public success class, runtime, `(H, Delta, B)`, approval-window configuration, and public commit. Protected within a successful bounded class: prior approval, provenance-history occupancy, approval/resume occurrence, number/order of internal mediation steps, serialized message sizes, and round timing.

The observed view includes ORAM physical paths, event classes, round count/order, actual serialized byte counts, actual timestamps/gaps, total duration, and commit position. Private labels are stored separately. Network endpoint privacy, OS/microarchitectural side channels, model-provider traffic, and fine-grained activity outside the instrumented transport are excluded.

## Invariants

- Authorization decisions were preserved; no DENY became ALLOW.
- Each successful run produced the same reference effect and sanitized result.
- Effect count was exactly one; dummy external effects were zero.
- Fixed M3 traces had the same operation/size projection.
- H=5 had no logical-horizon overflow; H=3 was rejected because overflow perfectly revealed the absent state.
- Exceptions and timeouts fail before commit in the tested core.

## Definition judgment

`NOT SUPPORTED`

The structural and size subclaims are supported, but the full definition requires `View(tau_0) ~= View(tau_1)` when timing is part of View. M3 aggregate timing AUC was 0.588 and all-features AUC 0.598. Agent Framework authorization timing reached 0.631. This is above the 0.5/permutation baseline and persists after full-work profiling, actual high-resolution barriers, and three repetitions.

The proof sketch remains conditional: if an implementation emits an identical real-time schedule and all internal work completes before its private-independent deadlines, the structural observer argument is sound. The Python live implementation does not satisfy that premise reliably. Occasional deadline misses and scheduler-level timing variation must either be eliminated by a stronger execution/transport boundary or explicitly moved into public leakage.

## Cross-session and failure boundary

ORAM leaf remapping prevents stable logical path tokens in the simulator, and no persistent action/agent handle is emitted. Public task identity remains intentionally linkable. Cadence phase is episode-local. A dedicated cross-session classifier over real distributed transports was not run; this remains P1.

Approval and internal-service exceptions abort before effect. Ambiguous external-effect recovery remains governed by Stage 7's idempotent operation-ID protocol; Stage 12 did not redesign it. Rare private retry/recovery timing was not comprehensively equalized.

