# Relay Security Definition — V9

The Relay game protects inner Agent/Tool action metadata using RFC 9458 over RFC
9292. Allowed public leakage includes Relay/Gateway endpoints, connection
policy, selected OHTTP key ID and KEM/KDF/AEAD, configuration epoch, public
profile, round count/order, lifetime, final sizes, and timing.

Mechanism status: **PASS at the local two-round component boundary**. Actual
OHTTP bodies traversed the frozen Relay byte-for-byte, private inbound headers
were dropped, and the Gateway recovered the private BHTTP action. The selected
public profile was development-only, so fixed-session structural and size
privacy remain OPEN. Timing remains OPEN / NOT_TESTED.

