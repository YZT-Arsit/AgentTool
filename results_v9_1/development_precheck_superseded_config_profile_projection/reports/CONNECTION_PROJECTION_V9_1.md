
# Connection Projection V9.1

The STRICT projection exposes Relay endpoint class, Gateway endpoint class,
connection count, first-seen-normalized reuse pattern, connection policy, and
session association. Raw diagnostics retain literal loopback source ports, but
those strings are neither required nor expected to match across runs. A changed
reuse pattern or reconnect changes the normalized projection and fails equality.
