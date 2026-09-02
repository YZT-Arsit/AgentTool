# V12 V4R7 smoke collector late-frame contract

This revision changes only the collection integrity decision. A V4R7 response deadline miss remains recorded with its release slip but is not an automatic integrity failure when all `R=521` opportunities, attempts, writes, Relay receipts, public slots, timestamps, and fixed sizes are complete and the frozen response no-catch-up recurrence holds.

Missing or duplicate slots, write failures, incomplete application-boundary timestamps, inconsistent transcript accounting, actual response catch-up, Registry ordinal corruption, infrastructure failure, and deployment/profile mismatch remain fail-closed conditions.

The immutable B40000 consumed session passed the corrected contract without reexecution. Observer projections, feature widths, classifier code, statistical thresholds, and the protected V4R7 runtime are unchanged. A new B50000-series manifest will be frozen before any fresh execution.
