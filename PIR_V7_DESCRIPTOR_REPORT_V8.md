# V8 AgentDescriptorV7 SimplePIR Report

## Result

`PIR_TO_V7_DESCRIPTOR = PASS` and `PIR_100K_V7_DESCRIPTOR = PASS`.

Fresh registries of authenticated 1,024-byte `AgentDescriptorV7` rows were
physically built and queried through the pinned official SimplePIR path with
full preprocessing. Five queries per scale included a repeated index. All 15
rows recovered exactly, authenticated, and matched the private expected Agent
ID. Repeated same-index queries had different serialized query bytes. Server
logs contained no Agent ID/name/capability, route, policy, descriptor digest, or
private class.

| Logical rows | Physical rows | Descriptor build | DB construction | Full preprocessing | Query | Server | Recovery | Upload + download | Client state | Peak memory |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,000 | 17.374 ms | 321.270 ms | 43.149 ms | 0.411 ms | 0.102 ms | 0.306 ms | 8,612 B | 8,798,208 B | 34,770,944 B |
| 10,000 | 10,000 | 262.255 ms | 3,156.139 ms | 1,260.934 ms | 4.256 ms | 4.360 ms | 1.400 ms | 23,208 B | 23,740,416 B | 171,814,912 B |
| 100,000 | 100,001 | 4,102.951 ms | 52,411.768 ms | 29,344.301 ms | 11.851 ms | 34.425 ms | 4.404 ms | 73,568 B | 75,309,056 B | 1,338,664,960 B |

The 100K physical database is 102,401,024 bytes: 100,000 logical rows plus one
1,024-byte parameter-padding row. These Windows local Go/CGO measurements are
new V8 results and are not merged with historical or V6 descriptor runs.

The harness's client/server roles share a process, so deployment isolation is
not measured. Cryptographic index privacy relies on the pinned SimplePIR
construction, not on absence of a classifier signal.

