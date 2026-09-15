# V15A real PSI/PIR public-profile feasibility closure

## Decision

The V14 mechanism is correct per explicitly invoked Agent access, but it does
not implement a complete session-level public Agent-access schedule. The
nearest frozen historical candidate is the V4R8 Registry profile: 100
opportunities, 60-ms spacing, a 6000-ms epoch, 25-ms initial lead, and at most
six real Agent resolutions.

Real 100K Microsoft APSI plus real 100K SimplePIR cannot sustain that cadence
on the measured host. V15A therefore does not activate a scheduler or silently
change Gamma. Three redesign proposals are recorded for a future predeclared
qualification.

## Required report

```text
BASE_V14_COMMIT:
4d1b9b7acacac3eb7daf996b331550aad2ecddce

PAPER_MODEL:
PREPROVISIONED_AGENT_ARTIFACT_STORE

REAL_APSI:
PASS

REAL_SIMPLEPIR:
PASS

PSI_SENDER_ITEMS:
100000

PIR_RECORDS:
100000 provisioned artifacts + 1 reserved dummy physical row

PIR_RECORD_BYTES:
1024

PUBLIC_AGENT_ACCESS_SLOTS_PER_SESSION:
NOT_IMPLEMENTED_IN_V14; historical V4R8 candidate tested = 100

PUBLIC_AGENT_ACCESS_INTERVAL:
NOT_IMPLEMENTED_IN_V14; historical V4R8 candidate tested = 60 ms

V14_PREVIOUSLY_EXECUTED_ONLY_LOGICAL_SLOTS:
YES

BYTES_PER_AGENT_ACCESS_SLOT:
2351400

PROJECTED_AGENT_ACCESS_BYTES_PER_SESSION:
235140000

PROJECTED_TOTAL_PUBLIC_BYTES_PER_SESSION:
236118959 (Agent access + frozen 978959-byte Gateway channel)

ACCESS_SLOT_LATENCY_P50:
129.002936 ms

ACCESS_SLOT_LATENCY_P95:
155.00429935 ms

ACCESS_SLOT_LATENCY_P99:
178.42015614 ms

MAX_SUSTAINABLE_SLOT_RATE:
2.8913566187 slots/s under the conservative observed-max criterion;
5.6047479255 slots/s under a p99 reciprocal criterion

CURRENT_PROFILE_FEASIBLE:
NO

PROFILE_REDESIGN_REQUIRED:
YES

FULL_SESSION_REAL_PSI_PIR_SCHEDULE:
NOT_RUN

FULL_SESSION_STRUCTURAL_EQUIVALENCE:
NOT_RUN

MAX_ADMITTED_AGENT_REQUESTS:
6 under the historical candidate contract; not enforced by a V14 scheduler

NEW_PRIVACY_ATTACK_EXPERIMENTS:
0

PAPER_FILES_MODIFIED:
NO

V15A_DECISION:
CURRENT_PROFILE_NOT_FEASIBLE
```

## Real per-slot measurement

The run used the V14 production binaries and databases: 100,000 APSI sender
items, 100,000 loadable artifact records plus one reserved dummy row, and
1024-byte authenticated records. It executed 300 microbenchmark slots (100
each deployed, unprovisioned, idle) and 500 scheduler slots. All 800
SimplePIR query hashes were distinct.

The measured all-case complete-slot latency was 129.003 ms p50, 155.004 ms
p95, 178.420 ms p99, and 345.858 ms maximum. Peak resident memory was
553,228 KiB for the APSI sender, 12,804 KiB for the APSI receiver, and
1,419,064 KiB for the SimplePIR process. Per-slot CPU observations are kept in
the raw CSV; process CPU can exceed wall time because the cryptographic server
uses multiple cores.

## Wire accounting

The V14 byte values were re-measured from the real serialized protocol
channels. Deployed, unprovisioned, and idle slots were exactly equal:

| Component | Request | Response |
|---|---:|---:|
| APSI OPRF | 104 B | 104 B |
| APSI query/result | 697,972 B | 1,579,652 B |
| SimplePIR | 36,388 B | 37,180 B |

This is 2,277,832 APSI bytes plus 73,568 SimplePIR bytes, or 2,351,400 bytes
per public Agent-access opportunity. A 100-slot session would use 235,140,000
Agent-access bytes; with the frozen 978,959-byte Gateway channel, the projected
total is 236,118,959 bytes (225.181 MiB). The historical 1.755 MiB/session
value does not include real APSI and is stale for this integrated design.

## Scheduler capacity

The scheduler used absolute, identical public timestamps for all-idle,
all-deployed, all-unprovisioned, alternating, and fixed-seed randomized mixes.
It did not schedule the next slot from completion. Nevertheless, each 100-slot
mix missed one nominal 60-ms interval on 98--99 slots, reached queue depth
51--52, and completed 6.109--6.571 seconds behind its final scheduled
opportunity. This is a capacity failure, not a class-dependent timing claim.

The smallest interval exceeding the maximum measured slot is 346 ms. Its
reciprocal, 2.891 slots/s, is the conservative observed zero-miss rate for this
host and lane configuration, not a future-host guarantee. The p99 reciprocal
rate is 5.605 slots/s; both are far below the required 16.667 slots/s.

## Unactivated redesign candidates

- `Gamma_candidate_1`: 180 ms, 34 slots in the 6-s epoch, 79,947,600 Agent-
  access bytes; p99-based proposal only.
- `Gamma_candidate_2`: 200 ms, 30 slots, 70,542,000 bytes; rounded engineering
  proposal with p99 headroom.
- `Gamma_candidate_3`: 350 ms, 18 slots, 42,325,200 bytes; exceeds the maximum
  observed slot by 4.142 ms but is still not a future reliability guarantee.

All retain the current conservative maximum of six admitted real Agent
requests. None is selected or activated in V15A.

## Claim boundary

Per-slot provisioned/unprovisioned/idle wire equality remains PASS. Complete
session-level structural equivalence is NOT RUN because the feasibility gate
failed. No linking, sequence, timing, AUC, 240-run utility, or Gamma-sweep
experiment was performed.

