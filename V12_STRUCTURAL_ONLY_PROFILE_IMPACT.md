# V12 structural-transcript profile impact

## Review decision

`REDEFINE_STRUCTURAL_TRANSCRIPT`

No concretely available platform provides a scheduling boundary materially
stronger than the failed container. This review therefore recommends separating
structural/size privacy from hard-deadline reliability. It does not implement
the change, choose a period, or execute a new profile.

## Proposed contract boundary

The proposed `STRUCTURAL_TRANSCRIPT_PROFILE` would protect only the ordered
public transcript after timestamp erasure:

- exactly the predeclared number of authenticated cells;
- exactly the predeclared request and response sizes;
- exactly the predeclared direction and authenticated session/slot order;
- one public profile independent of Agent, Tool, action count, repetition, and
  result-readiness secrets.

Actual emission and receive timestamps, inter-cell gaps, scheduler lateness,
completion span, packet timing, and host traffic analysis remain observable and
outside the claim. A late public cell is still emitted in its authenticated
order; lateness must not truncate the cover transcript. This is not timing
indistinguishability.

Semantic fail-closed behavior remains separate. A real operation that misses a
private or provider contract cannot be silently reported as successful, but the
predeclared NOOP/WAIT cover transcript must continue. No dummy provider action,
secret-dependent extra cell, retry, replacement, or session shortening is
permitted.

## Required claim changes

### Threat model

The observer is explicitly allowed to learn all timestamps and scheduling gaps.
The theorem covers only count/size/direction/order and the already-declared
endpoint/session/connection structure. Host delay, suspension, and denial of
service remain excluded. A public, secret-independent campaign liveness limit
is needed to avoid an unbounded wait, but reaching it is an infrastructure
failure rather than a structural-privacy PASS.

### Formal statement

Replace any hard-cadence premise with equality of timestamp-erased,
authenticated public-cell sequences. State a liveness/fairness assumption for
eventual emission. Do not infer packet-timing privacy, global traffic-analysis
resistance, or a deadline guarantee from structural equality.

### Structural and size projections

`canonical_v9_1/projection.py` already excludes timestamps and mechanically
requires the frozen round count and order. That core is compatible in shape,
but `scheduled_public_lifetime_ns` must be described as nominal public policy,
not proof that the last cell arrived by a hard deadline. Lateness stays solely
in `timing_network_diagnostics` and private scheduler diagnostics. Prefix
projections remain authenticated slot-order prefixes, never wall-clock
prefixes.

### Profile definition

`v11_4/profile.py` currently derives a scheduled lifetime as
`total_rounds * round_period_ms`. A structural profile would need to distinguish
nominal slot targets from the transcript-completion contract. Its ID and public
schema must explicitly name the structural-only class and must not reuse the
meaning of the old `STRICT-ONLINE` hard-deadline evidence.

### Runtime semantics

`common_action_gateway_v2/canonicalv9/online.go` currently marks a crossed slot
as missed and omits its transmission. Implementing the proposed contract would
require a separately reviewed emission state machine that retains every cell
and emits it once in authenticated order despite lateness. The change must not
introduce secret-dependent catch-up, extra cells, reordering, or provider work.
`runner.go` would need distinct infrastructure-lateness and transcript-complete
statuses. The absolute pacer remains useful performance engineering, but is no
longer a privacy premise.

## Evidence and experiment impact

Historical freezes and failures remain immutable. New append-only evidence
would be required for the changed contract:

1. Requalify the public profile for exact cell count, size, direction, order,
   session, endpoint, connection reuse, and authenticated slot binding under
   injected and naturally observed scheduler stalls.
2. Rerun all P1-P14 structural pairs and corrected prefix checks using actual
   Relay observations. A pair is valid only after both arms are functionally
   valid and both complete the full transcript.
3. Rerun B4/B5 structural/size cells because their runtime dependency includes
   the changed scheduler/emission state machine. Preserve B0-B3 unless a
   dependency audit shows that their executable path changed.
4. Add ablations for hard-deadline truncation versus emit-all structural
   behavior, absolute pacer on/off, affinity on/off, and injected public
   scheduler stalls. Report these as reliability/performance ablations, not
   privacy amplification.
5. Report nominal period, actual completion span, lateness distribution,
   infrastructure failures, CPU/RSS, and bytes separately. No timestamp-based
   classifier may be used to claim timing privacy.
6. Rerun affected scheduler, result-delivery, operation-binding, recovery, and
   session-finalization negative tests.

The frozen `PUBLIC_LIFETIME_CONTRACT_V9_1.md`,
`V11A_STRUCTURAL_DECISION_RULES.md`, and
`V11B0_1_FINAL_DECISION_RULES.json` remain historical evidence. Any future
decision rules must be new artifacts: they must replace the old
zero-scheduler-miss functional prerequisite with full-transcript completion
plus separately reported infrastructure lateness. Existing results must not be
retrospectively regraded.

## Unchanged boundaries

- `HISTORICAL_PROVIDER_ERROR = NOT_REPRODUCED_UNRESOLVED`.
- The 1,498/1,498 fresh `PROVIDER_OK` observations remain evidence only.
- Timing privacy remains `OPEN / NOT TESTED`.
- Packet-level timing remains `OPEN`.
- No new period, universe, seed, holdout manifest, or selected execution is
  authorized by this review.

