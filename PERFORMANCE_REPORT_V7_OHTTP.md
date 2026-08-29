# Performance Report V7-OHTTP

## Measured foundations

Official SimplePIR remains the measured private Agent-selection foundation. At
100,000 logical rows the frozen integration reported 6.643 ms mean query
generation, 14.046 ms server answer, 2.950 ms recovery, 36,388-byte upload,
37,180-byte download, and 75,309,056 bytes persistent client state. Full
preprocessing was 23,506.850 ms in that run.

The pre-OHTTP V7 reliability gate executed 161 real local provider effects,
delivered 161 results, and executed zero dummy heavy operations. It is retained
only to characterize the queue/journal/admission machinery.

## Not measured

No RFC 9458/BHTTP backend was available offline. Therefore OHTTP key setup,
BHTTP encoding, HPKE encapsulation/decapsulation, final encapsulated sizes,
Relay/Gateway HTTP overhead, and full V7-OHTTP latency are unmeasured. No values
are extrapolated from the legacy framing.

