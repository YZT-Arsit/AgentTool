
# Public Lifetime Contract V9.1

For `V9_1-STRICT-H50-P1`, scheduled start is the public monotonic session T0
selected when the session is accepted. Scheduled end is T0 plus
555000000 ns (111 rounds x
5 ms). The round budget is fixed from public capacity,
not completion. NOOP/WAIT continues through the fixed final round.

The frozen V9 runner does not export the exact connection-close timestamp.
V9.1 records Relay observation span and wrapper elapsed time separately, marks
connection-close slip `NOT_CAPTURED_BY_FROZEN_V9_RUNNER`, and makes no timing
privacy claim. Timing and packet-level timing remain OPEN.
