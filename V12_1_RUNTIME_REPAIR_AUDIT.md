# V12.1 generic reliability repair audit

The repair contains no case-ID, count-50, selected-holdout, or profile-extension branch. Wire formats, OHTTP/BHTTP sizes, endpoints, round count, order, and the V11.4 public profile remain unchanged.

## Durable-state path

The old effect journal and ready queue rewrote, `fsync`ed, closed, and renamed a growing JSON snapshot on every state transition. A 50-action session performed multiple synchronous whole-file transitions per action on the result-critical path. V12.1 replaces those snapshots with versioned append-only WAL records, atomically migrates a legacy snapshot on its first mutation, and fails closed on malformed WAL records. `EffectRecoveryJournal.Begin` persists a fresh operation directly as `PROVIDER_STARTED`, eliminating a redundant ACCEPTED write while retaining restart rules for read-only, idempotent, and non-idempotent effects. Ready-queue `IN_FLIGHT` remains deliberately in memory: a crash replays the last durable READY record and the trusted client deduplicates by `operation_id`, preferring duplicate-safe replay over silent loss.

## Scheduler rule

The prior code treated both `launch_slip > scheduler_tolerance` and `launch_slip >= round_period` as missed slots. V12.1 records the former as `diagnostic_tolerance_exceeded`; only crossing the next public slot deadline is a schedule miss. It still never submits an expired slot and never creates a catch-up burst.

## Diagnostics

Transport failures now distinguish non-200 status, response-read failure, response-size mismatch, and generic transport error with public slot/status/observed/expected byte fields. Development summaries expose exact private operation-ID lifecycle sets separately from Relay evidence. Neither change enters the structural or size projections.

Focused Go tests cover one-transition provider start, crash replay, sub-period static/online launch slip, and true crossed-deadline failure. The decisive reliability and full regression results are reported separately; this audit does not infer PASS from implementation alone.
