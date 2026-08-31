# V12 Timing Observer Projections

## PIR Registry view

The Registry projection contains only application-channel query/response timing, inter-query gaps, total span, fixed PIR sizes and dimensions, and public schedule/configuration fields. It excludes the queried index, logical Agent identity, operation IDs, routes, secret labels, real/dummy classification, and private host diagnostics.

## OHTTP Relay view

The Relay projection contains only application-channel request/response timestamps, inter-cell gaps, per-cell response delays, total span, fixed public sizes, authenticated session/slot order, profile, endpoint class, HTTP version, and connection policy. It excludes OHTTP plaintext, logical action/Agent identity, operation IDs, private route aliases, readiness, and all private provider/host diagnostics.

## Provider and joint views

The provider sees its own invocation and is not treated as an invocation-hiding observer. Registry and Relay are evaluated separately. No joint Registry+Relay dataset is authorized by this threat model.

One complete session/workflow is the statistical sample. Cells within a session are not treated as independent observations.
