# Real PIR Integration Report

## Verdict

`REAL_PIR_CORRECTNESS = PASS`, `REAL_PIR_100K_OPERATIONAL = PASS`, and
`REAL_PIR_FULL_PREPROCESSING = PASS`.

The B2 candidate path now retrieves the actual 1,024-byte Agent capsule with the official
[ahenzinger/simplepir](https://github.com/ahenzinger/simplepir) construction and feeds that recovered capsule into
`AgentControlExecutor`. The mock lookup is not used in the final closure experiment.

## Provenance

- Repository: `https://github.com/ahenzinger/simplepir`
- Audited commit: `e9020b03bf2872c75b8954e749e32408b5db87ed`
- License: MIT (`external_pir/simplepir/LICENSE`)
- Local checkout: `external_pir/simplepir/`
- Integration bridge: `pir_integration/simplepir_bridge/`
- Upstream correctness check: `go test -run TestSimplePir -count=1 -v`; all official SimplePIR tests passed.

The bridge uses upstream `PickParams`, `Init`, `Setup`, `Query`, and the SimplePIR arithmetic. It does not use the
upstream benchmark shortcut that replaces preprocessing with random hints. `Setup` was executed and timed for every
scale run.

## 100K database and full path

| Property | Measured value |
|---|---:|
| Logical rows | 100,000 |
| Physical row capacity | 100,001 |
| Logical bytes | 102,400,000 |
| Physical bytes | 102,401,024 |
| Padding | 1,024 bytes |
| Database construction | 1,377.154 ms |
| Shared-state generation | 506.416 ms |
| Full preprocessing (`Setup`) | 23,506.850 ms |
| Hint | 38,072,320 bytes |
| Persistent client state | 75,309,056 bytes |
| Mean query generation | 6.643 ms |
| Mean server answer | 14.046 ms |
| Mean client recovery | 2.950 ms |
| Online upload / download | 36,388 / 37,180 bytes |
| Peak allocated memory | 1,444,030,464 bytes |
| Correct queries | 10 / 10 |

The tested indices included both endpoints and repeated indices:
`0, 1, 17, 999, 9999, 50000, 77777, 99999, 17, 99999`. Recovered capsule IDs and full record bytes matched the
source registry.

## Server-view audit

The server log contains only query ordinal, fixed query dimensions/bytes, fresh query digest, answer bytes and time,
and the common `SimplePIRServer` identity. It contains no logical index, Agent name, capsule hash, class label, or
target-derived file offset. Client labels and indices are stored in a separate private artifact.

Repeated queries for indices 17 and 99,999 had different raw query bytes and SHA-256 digests. Freshness comes from
the upstream cryptographic PRG invoked by each `Query` call. No target-specific seed or cached query is reused.

This log audit is a leakage sanity check, not the basis of the cryptographic claim. Query-index privacy relies on the
audited SimplePIR construction and its assumptions.

## Windows portability deviation

The official packed C multiplication kernel crashed at the 100K parameter shape because the selected row dimension
(`L = 9295`) is not divisible by eight while that kernel consumes rows in groups of eight. The integration therefore
runs the upstream setup and query algorithms, then unsquishes the database and calls upstream exported
`MatrixMulVec` for the mathematically equivalent server answer. This changes the storage/answer implementation and
performance profile, not the PIR query construction. It is an engineering adapter, not an upstream result or a new
cryptographic primitive.

## Limits

- The 100K registry is physically real but is a generated scale-up of the 22 framework-native Agent prototypes; it is
  not 100,000 independently authored Agents.
- Peak memory was about 1.44 GB and persistent client state about 75.3 MB. Operational does not mean optimized.
- The experiment does not provide a fresh cryptographic proof for the adapter.
- Server answer timing remains measurable and is treated as an open timing channel.

Machine-readable results are in `REAL_PIR_100K_RESULTS.csv`; raw server/client traces and raw length-prefixed query
bytes are under `results_crypto_closure/scale_*`.
