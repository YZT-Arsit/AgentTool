# V11.4.1 projection diff

The exact Linux-frozen `canonical_v9_1/projection.py` was retrieved read-only from the V11.4 qualification host. Its SHA-256 is `4b1181261eb012e9554b69538e371a1f12bd8e4364024c10022160d5bd0e0655`. The projection committed at `f6860baaab8927f9b0b66153959b55d8ca072c23` has SHA-256 `3a9fc710f98c586e98be64b04e5c8875f8297906199458199340b41fb981f9ea`.

The semantic diff contains exactly three additions and no removals:

- `public_session_ids`
- `client_http_versions`
- `gateway_http_versions`

No other code or projection semantics differ. The committed stronger projection is therefore adopted as the candidate final analysis projection; the three fields were not removed to recover the old hash. Raw timestamp fields remain evidence but are absent from structural and size equality.

```diff
--- linux-frozen/canonical_v9_1/projection.py
+++ git-f6860baaab8927f9b0b66153959b55d8ca072c23/canonical_v9_1/projection.py
@@ -53,6 +53,7 @@
         "gateway_endpoint_class": [str(event["gateway_endpoint"]) for event in events],
         "session_count": profile.session_count,
         "session_association": [1] * len(events),
+        "public_session_ids": [int(event.get("session", 1)) for event in events],
         "connection_count": {
             "relay_client": client_count,
             "relay_gateway": gateway_count,
@@ -64,6 +65,8 @@
         "connection_policy": profile.connection_policy,
         "round_count": len(events),
         "round_order": [int(event["round"]) for event in events],
+        "client_http_versions": [str(event.get("client_http_version", "")) for event in events],
+        "gateway_http_versions": [str(event.get("gateway_http_version", "")) for event in events],
         "request_length_sequence": [int(event["request_length"]) for event in events],
         "response_length_sequence": [int(event["response_length"]) for event in events],
         "scheduled_public_lifetime_ns": profile.scheduled_lifetime_ns,
```
