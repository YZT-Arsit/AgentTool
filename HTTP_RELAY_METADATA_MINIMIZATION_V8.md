# HTTP Relay Metadata Minimization — V8

Status: **PARTIAL (`NOT_COMPLETED_ENVIRONMENT` for runtime tests)**

The V8 relay in `common_action_gateway_v2/v8/http_relay.go` creates a fresh outbound HTTP request to a configured loopback Gateway. It copies no arbitrary inbound headers. Its explicit outbound allowlist is limited to deployment-required `Content-Type` and the body-derived `Content-Length`; method and Gateway URL come from public configuration.

The code does not forward `Forwarded`, `X-Forwarded-For`, `Via`, `Cookie`, `Authorization`, inbound `User-Agent`, arbitrary `X-*` headers, or TLS client metadata. It forwards the body bytes without parsing inner BHTTP, owns no OHTTP key, creates no route handle, and records no body digest. Relay-client and Relay-to-Gateway connection identifiers are distinct fields.

Evidence:

- `go test -c ./v8`: PASS (test binary built).
- `go vet ./v8`: PASS.
- Runtime execution of the new V8 test binary: `NOT_COMPLETED_ENVIRONMENT`; Windows Application Control blocked the generated executable. No bypass was attempted.

Therefore this is not promoted to a runtime PASS. The canonical OHTTP relay remains blocked independently by the missing RFC implementation.

