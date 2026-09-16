# V15E final access-capture closure

## Decision

```text
ACCESS_EVIDENCE_CLOSED
```

The fresh final dataset contains 4,000 complete three-access sessions and
12,000 complete logical Agent-access observations. The fixed four-slot public
profile produced 16,000 APSI observations and 16,000 SimplePIR observations.
Collection failures, incomplete observations, retries, replacements, and
discarded observations were all zero.

## Frozen system and dataset

- Real Microsoft APSI v0.13.1 labeled PSI over the 100K sender.
- Real SimplePIR over 100,000 fixed 1,024-byte artifact records plus one dummy row.
- `R_A = 4`, `Delta_A = 350 ms`, maximum three admitted real accesses, and the frozen one-slot pipeline.
- Balanced `AAA`, `ABA`, `AAB`, and `ABC` classes: 1,000 sessions per class.
- Grouped split frozen before collection: 600 TRAIN, 200 VALIDATION, and 200 TEST sessions per class.
- Disjoint concrete AgentID partitions: TRAIN 1001--1600, VALIDATION 1601--1800, TEST 1801--2000.

## Application-protocol capture

The primary transcript source was the real server-side application protocol
boundary, not pcap. A transparent ZeroMQ APSI wrapper observed each multipart
message before forwarding it unchanged. The real SimplePIR bridge observed the
serialized query and answer matrices at its server boundary. No AgentID, PIR
row, match bit, real/dummy flag, artifact plaintext, or TEE diagnostic entered
the public capture.

Every exact serialized object was consumed in full by a pre-frozen compact
representation: SHA-256, a 32-bin byte histogram, and 64 fixed-offset bytes.
Raw ciphertext copies were not retained after this representation was formed.
This is the same kind of bounded representation used by the frozen V15D attack
methodology, now applied without packet loss to all six protocol objects.

| Object | Serialized bytes | Application messages |
|---|---:|---:|
| APSI OPRF request | 104 | 1 |
| APSI OPRF response | 104 | 1 |
| APSI query | 697,972 | 1 |
| APSI result | 1,579,652 | 9 |
| SimplePIR query | 36,388 | 1 |
| SimplePIR answer | 37,196 | 1 |

The APSI result-message lengths were exactly
`[68, 197448, 197448, 197448, 197448, 197448, 197448, 197448, 197448]`.
The historical 37,180-byte SimplePIR answer value is the matrix payload size;
37,196 bytes is the exact serialized object including its 16-byte dimension
header. Public-profile accounting remains unchanged.

Each object records direction, exact length, message boundaries, SHA-256, and
server-side monotonic application timestamps. Public slot is derived exactly
as `observation_ordinal mod 4`; session-relative timestamps are derived within
each server clock domain from that session's first receive event. No APSI to
SimplePIR cross-process clock subtraction is used. These are
`APPLICATION_PROTOCOL_TIMESTAMP` observations, not packet-level timestamps.

## Completeness and integrity

```text
planned sessions                         4000
complete sessions                        4000
failed sessions                             0
logical Agent-access observations       12000
public Agent-access slots               16000
complete APSI captures                  16000
complete SimplePIR captures             16000
incomplete observations discarded           0
CAPTURE_COMPLETENESS                      100%
```

The four ordinal domains were complete and unique. All logical samples bind
`APSI_j` to `SimplePIR_(j+1)`, matching the frozen pipeline; bootstrap and drain
PIR operations were not mislabeled as the current Agent access. Collection was
completed and hash-closed before any classifier fit or class-conditioned
summary.

## Statistical protocol

The frozen attacker families were Logistic Regression, Extra Trees,
HistGradientBoosting, and RBF SVM. Model selection used TRAIN/VALIDATION only;
score direction used grouped TRAIN out-of-fold predictions only. TEST remained
held out. Every reported interval and randomization test uses 10,000 grouped
resamples. Unprotected visible-AgentID controls use the same splits and
statistics and achieve 1.0 on every task.

## Principal protected results

| Task (ALL view) | Held-out result | 95% CI | Randomization p |
|---|---:|---:|---:|
| Same-Agent linking | AUC 0.487 (orientation-invariant 0.513) | [0.446, 0.526] | 0.7383 |
| Cross-session, same slot | AUC 0.519 | [0.490, 0.547] | 0.1009 |
| Cross-session, cross slot | AUC 0.472 (orientation-invariant 0.528) | [0.444, 0.501] | 0.9712 |
| Four-class ordering/recurrence | accuracy 0.256 | [0.226, 0.286] | 0.3530 |
| Rare insertion (`AAA` vs `AAB`) | AUC 0.525 | [0.467, 0.582] | 0.2011 |
| Recurrence (`AAA` vs `ABC`) | AUC 0.463 (orientation-invariant 0.537) | [0.407, 0.521] | 0.8919 |
| Return pattern (`ABA` vs `ABC`) | AUC 0.551 | [0.495, 0.608] | 0.0389 |

The complete evidence supports the first six access claims under the frozen
observer and statistical protocol. Return-pattern privacy is not established:
the ALL-view permutation result is significant even though its grouped CI
includes 0.5. This negative result is retained.

No utility, scale, Gateway timing, branch timing, or structural-equivalence
campaign was rerun. V15D's timing limitations remain unchanged. V15E closes
the access-transcript evidence gap; it does not establish realized timing
privacy.
