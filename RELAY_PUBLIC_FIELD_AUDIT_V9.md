
# Relay Public Field Audit V9

Status: **PASS**.

Allowed fields: `['aead_id', 'config_epoch', 'gateway_endpoint', 'kdf_id', 'kem_id', 'ohttp_key_id', 'profile_id', 'relay_client_connection_id', 'relay_endpoint', 'relay_gateway_connection_id', 'request_length', 'request_observed_ns', 'response_length', 'response_observed_ns', 'round']`. Every final functional session had one reused client-Relay connection and one reused Relay-Gateway connection. All request bodies were 1079 bytes and all responses 800 bytes. Round event count equaled the public profile round count.

No Agent ID/name, Tool/provider name, private route handle, operation ID, protected arguments, authorization, cookie, client authorization, Forwarded, X-Forwarded-For, or client-identifying Via was present in public Relay events. Private correctness logs remain separate.
