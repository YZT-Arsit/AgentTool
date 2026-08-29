
# Canonical Route Activation Audit V9

Status: **PASS**.

Relay event schema is exactly: `['aead_id', 'config_epoch', 'gateway_endpoint', 'kdf_id', 'kem_id', 'ohttp_key_id', 'profile_id', 'relay_client_connection_id', 'relay_endpoint', 'relay_gateway_connection_id', 'request_length', 'request_observed_ns', 'response_length', 'response_observed_ns', 'round']`. Forbidden private keys found: `[]`. Private operation/route tokens found in public values: `[]`.

The final rerun uses public profile IDs such as `V9-FUNCTIONAL-100-PUBLIC-ACTIONS-58`; it does not encode Agent identity. An earlier audited run did encode Agent labels in `profile_id`; it is preserved under `results_v9/canonical_runner_failed_target_derived_profile_20260829/` and excluded from passing evidence.

Private provider selection occurs only after OHTTP decapsulation through `route_handle -> trusted route table -> loopback endpoint`. The Relay does not parse the body and records only fixed `LOCAL_RELAY` / `LOCAL_GATEWAY` endpoint labels. Per-session HTTP connections were reused; the development runner creates separate public sessions sequentially.
