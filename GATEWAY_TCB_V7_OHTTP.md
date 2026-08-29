# Gateway TCB V7-OHTTP

## Current code inventory

- `common_action_gateway_v2/v7ohttp`: 268 physical non-test lines across six
  Go files for contracts, public-profile validation, exact-byte Relay model,
  application association, and legacy classification.
- `common_action_gateway_v2/v7`: 742 physical non-test lines across five Go
  files for admission, lifecycle, ready queue, effect recovery, and the legacy
  frontend integration.
- Pre-existing Gateway V2 package: 1,890 physical non-test lines across 16 Go
  files; portions are provider/worker/journal/scheduler substrate, while custom
  protocol/frontend portions are excluded from the canonical wire.

Counts are physical-line engineering measures, not security complexity scores.

## Canonical trusted Gateway dependencies

The intended Gateway TCB includes RFC 9458 decapsulation/response
encapsulation, RFC 9292 parsing/encoding, private schema validation, route
resolution, authorization checks, provider adapters, effect journal, durable
ready queue, and public response scheduler. The OHTTP third-party dependency is
not present and therefore contributes zero integrated lines today; this is a
missing implementation, not a small-TCB success.

The Cloud Relay's  opaque forwarding contract is untrusted and outside the
Gateway TCB. Providers remain outside and learn their own invocations.
