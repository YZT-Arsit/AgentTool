# Current V6 security definition

For two executions with the same public profile and allowed leakage, V6 defines
separate views.

For `O_registry`, the selected fixed-width row should be computationally hidden
by official SimplePIR; descriptor plaintext should be AEAD-confidential and
authenticated. This implementation path passes correctness and falsification
checks at 100K, while the cryptographic claim is inherited from the pinned
scheme—not from classifiers.

For `O_cloud_network` in STRICT, the intended structural view contains one
common Gateway endpoint, fixed request/response cell width, fixed slot
count/order, one public connection/profile, and no route/Agent/Tool identifiers.
The live V6 paired experiment did not pass functionality and was not completed,
so this end-to-end claim remains OPEN rather than inferred from format tests.

For `O_cloud_host`, no hostile-host action-identity claim is made by the local
backend. A future attested TEE/CVM must protect capability resolution, PIR client
state/recovery, descriptor plaintext, route handles, and keys.

Fine timing, packet-level timing, resource/microarchitectural leakage, global
traffic analysis, arbitrary human timing, denial of service, rollback without
an external freshness anchor, and provider-side observation are excluded/open.
PIR does not hide activation, TLS does not hide destination metadata, and the
Gateway does not hide an invocation from its destination provider.
