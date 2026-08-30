# V12 provider diagnostics audit

V12-RC remains permanently failed, and its retained identity
`DEV-RC-OA-REPEAT10-007` was not rerun.

## Private diagnostic implementation

The canonical Go engine now classifies every completed provider attempt into
one of eight private classes: `PROVIDER_OK`, transport error, context deadline,
HTTP non-2xx, response decode error, provider-status error, oversized response,
or internal other error. The record includes operation/route identifiers,
monotonic request and return times, elapsed time, the fixed context deadline,
bounded byte count, HTTP status, decode state, decoded provider status, and a
private error type/string when present.

The public `ResultRecord` mapping is unchanged: success remains `StatusOK` and
all diagnostic failure subclasses retain the existing `StatusError` behavior.
No retry was added.

The DEV `V11EvidenceProviders` records a separate private handler lifecycle:
request receipt/decoding, logical completion, response status/length/write,
socket-write exception class, and elapsed time. It records neither protected
arguments nor credentials.

Deterministic Linux fault injection passed all six required classifications:

1. HTTP 200 plus status OK -> `PROVIDER_OK`;
2. transport failure -> `PROVIDER_TRANSPORT_ERROR`;
3. deadline expiry -> `PROVIDER_CONTEXT_DEADLINE_EXCEEDED`;
4. HTTP 503 -> `PROVIDER_HTTP_NON_2XX`;
5. malformed JSON -> `PROVIDER_RESPONSE_DECODE_ERROR`;
6. decoded status ERROR -> `PROVIDER_STATUS_ERROR`.

Two Python tests also passed on Linux: private provider evidence contains the
required lifecycle without arguments, and adding private diagnostics leaves
the strict structural and size projections byte-for-byte unchanged.

## One-shot diagnostic campaign

The first output root records a harness preflight failure before any raw
workflow existed: the initial DEV permit string was rejected by the frozen
orchestrator. It remains preserved and contains zero executed units. The actual
one-shot campaign used a new output root and the frozen manifest SHA-256
`acad7430010876c8c9a09831ac4fd88d91b3933bafaa8e7213b944e9a0e21045`.

- OpenAI repeated-name depth-10: 100/100 complete.
- Microsoft repeated-name depth-10: 49/100 complete; the next workflow failed;
  50 were not run.
- Provider attempts observed: 1,498.
- Provider diagnostic classes: 1,498 `PROVIDER_OK`, zero other classes.
- Retry/resume/substitution: none.

The new failure is `DEV-PC-DIAG-MS-REPEAT10-049`. Its first eight provider
transactions were `PROVIDER_OK` in 0.674--1.488 ms. The public scheduler then
missed slots 22, 23, and 24 with launch slips 33.506527, 23.508191, and
13.509163 ms. The session emitted 353/356 rounds and failed as
`SESSION_SCHEDULE_FAILURE`; eight results were delivered, a ninth operation was
accepted but remained pending, and the tenth framework call observed the
session failure.

This is not evidence for any provider-error subclass. The retained V12-RC
provider `ERROR` did not recur before the independent schedule failure stopped
the frozen campaign. Its exact root cause therefore remains
`NOT_REPRODUCED_UNRESOLVED`. Claiming transport, deadline, HTTP, decoding, or
provider-status causation would fabricate evidence.

Per the predeclared gate, no generic provider repair, post-repair reliability
campaign, Class-A suite, Go gate, profile requalification, B4/B5 performance,
privacy/security regression, candidate universe, seed, or holdout was run.
