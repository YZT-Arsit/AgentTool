# Performance Report — V9

Only protocol development costs were measured. Required fixed buckets are 1024
bytes BHTTP request and 768 bytes BHTTP response. With the selected development
suite, final OHTTP sizes are 1079 request bytes and 800 response bytes.

The final recorded V9 Go adapter/Relay suite completed in 0.043 seconds. This is
test-suite wall time, not a latency benchmark. The post-OHTTP 1K SimplePIR smoke
recovered 4/4 authenticated descriptors. Full preprocessing setup was 155.039
ms; mean query generation/server answer/client recovery were 2.35825/0.3615/
1.48975 ms, with 2020-byte upload and 6592-byte download per query. These are a
small regression smoke, not replacements for frozen 100K measurements.

Canonical OHTTP end-to-end latency, scheduler slip, and B0-B6 performance are
`NOT_RUN`. Frozen V8 1K/10K/100K PIR measurements remain valid and separate.
