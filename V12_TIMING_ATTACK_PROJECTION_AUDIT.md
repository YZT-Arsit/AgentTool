# V12 timing attack projection audit

The Relay classifier receives only within-session request/response timing, gaps, request-response durations, total span, and fixed public metadata. The Registry classifier receives only within-session query/response timing, gaps, total epoch span, and fixed public PIR metadata. Absolute time, execution order, randomized block ID, private identifiers, real/dummy labels, readiness state, and scheduler/host diagnostics are excluded. The claim is conditioned on a public session existing.
