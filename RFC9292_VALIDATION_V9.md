# RFC 9292 Validation — V9

Status: **PASS**

The V9 codec delegates known-length Binary HTTP framing to the vendored
`ohttp-go` implementation. Its private application body is strict JSON and is
not presented as a replacement for BHTTP.

Validated request cases: `NOOP`, `REAL_TOOL`, `REAL_AGENT_SERVICE`, and
`REAL_EXTERNAL_HTTP`. Validated response cases: `WAIT`, `RESULT`, `ERROR`,
`TIMEOUT`, `EFFECT_OUTCOME_UNKNOWN`, and `PROFILE_OVERFLOW`. Tests cover
semantic round trips, nonzero padding rejection, unknown-length indicator
rejection, fixed buckets, and case-insensitive decoded HTTP field names.

The common inner target remains
`https://action-gateway.invalid/v1/agent-slot`; no downstream endpoint appears
in the outer HTTP request.

