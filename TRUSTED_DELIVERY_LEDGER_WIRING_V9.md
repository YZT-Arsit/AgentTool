# Trusted Delivery Ledger Wiring — V9

Status: **PARTIAL / NOT WIRED TO REAL OHTTP RESPONSE**

The frozen V8 ledger regression passed locally (11/11 V8 tests overall), and
real OHTTP response decapsulation plus BHTTP decoding now pass independently.
The full sequence `decapsulation -> BHTTP decode -> DeliveryLedger -> framework
callback` is not implemented in one canonical executable, so component tests
are not promoted to live wiring evidence.

The callback-after-effect/before-durable-delivery-commit ambiguity remains
explicit. Exactly-once framework delivery is not claimed.

