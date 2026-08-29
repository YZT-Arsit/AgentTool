# V10 long-horizon structural rules (frozen)

For every applicable structural pair, V10B must recompute the accepted structural and size projections from raw Relay events and check aligned prefixes at exactly:

`1, 5, 10, 25, 50, 111` public rounds.

Each prefix check is exact and uses only count, order, suite/profile metadata, normalized connection structure, endpoint classes, and actual observed message sizes. It must not use send/receive timestamps. The full 111-round comparison remains mandatory even when every shorter prefix is equal.

No pair, arm, sequence, horizon, or projection may be changed after observing V10B results.
