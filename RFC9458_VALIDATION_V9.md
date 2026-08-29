# RFC 9458 Validation — V9

Status: **IMPLEMENTATION PASS; APPENDIX A BLOCKED**

| Check | Result |
|---|---|
| Upstream OHTTP tests | PASS (OHTTP tests in the 18-test upstream run) |
| Key configuration parsing/round trip | PASS |
| Multiple Gateway configs | PASS upstream |
| Multiple advertised suites parse/round trip | PASS V9 |
| Request/response round trip | PASS |
| Fresh per-slot context | PASS |
| Context reuse rejection | PASS |
| Wrong-slot response rejection | PASS |
| Modified response rejection | PASS |
| Truncated response rejection | PASS |
| Unconfigured request suite rejection | PASS |
| Appendix A byte-exact vector | BLOCKED_VECTOR_NOT_SUPPLIED |

The adapter in `common_action_gateway_v2/v9ohttp/ohttp_backend.go` uses the
vendored implementation's RFC APIs. It adds validation and one-use context
guards but no custom HPKE or AEAD construction. The ordinary round-trip result
is not mislabeled as Appendix A conformance.

