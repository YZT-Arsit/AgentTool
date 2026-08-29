# Internal result multiplexer V11

`PrivateResultMultiplexer` accepts fixed logical results from `LOCAL_TRUSTED_RESULT` or `OHTTP_GATEWAY_RESULT`, rejects duplicate submissions/unknown sources, and delivers through the existing trusted `DeliveryLedger`. Replay suppression is tested. The documented non-atomic framework-callback versus durable `FRAMEWORK_DELIVERED` update remains PARTIAL; no general exactly-once claim is made.
