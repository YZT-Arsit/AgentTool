# V12 timing statistical protocol V3

This pre-outcome methodology revision supersedes statistical protocol commit `3dde92221b274148f4926de4d4df07d8a6c64cd5` only for Relay application-observer ordering and feature semantics. No protected classifier or AUC existed when the defect was discovered.

## Relay integrity and timing representation

Logical public-slot completeness and application-observed arrival order are separate contracts. A complete one-session Relay trace has exactly `R` events, exactly one public slot ID `1..R`, fixed public sizes, one session/profile, and complete valid application response-send timestamps. It need not arrive at the application in slot-number order.

The V3 timing-only representation is fixed-width and preserves reordering:

- slot-indexed session-relative request timestamps, width `R`;
- chronological request inter-arrival gaps, width `R-1`;
- slot-indexed session-relative response-send timestamps, width `R`;
- chronological response-send inter-arrival gaps, width `R-1`;
- request/response delay paired by public slot, width `R`;
- total observed session span.

The origin is the minimum application request-arrival timestamp. Slot-indexed timestamps may be non-monotone. No separate arrival-rank permutation is included because the slot-indexed timestamp vector already determines it; omitting a duplicate encoding does not discard reordering.

## Registry ordering

Registry retains its stricter ordinal/timestamp contract. The fixed PIR cover schedule has one thread that performs each ordinal synchronously through a query-locked request/response channel. The pinned SimplePIR bridge consumes one request, emits and records one response, and only then increments the ordinal. No parallel Registry request path was found.

## Statistical decisions preserved

Matched pairs, TRAIN-only model selection and score orientation, the four frozen model families, one decisive EVAL model, 10,000 complete-block bootstrap resamples, `UCB95 <= 0.55`, and the sentinel `LCB99.5 > 0.55` early-failure rule remain unchanged. Campaign-specific denominators and permanent exclusions are not changed. No protected session, classifier training, AUC, or protected bootstrap was run for this repair.
