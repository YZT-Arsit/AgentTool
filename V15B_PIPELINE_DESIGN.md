# V15B fixed one-stage Agent-access pipeline

## Public construction

`Gamma_A` is independent of the frozen V4R8 Gateway channel `Gamma_G`. Every
public Agent-access slot contains exactly one fresh labeled APSI operation and
one fresh SimplePIR operation. The protocols run concurrently, but neither is
skipped.

For slot `j`:

1. the PSI stage consumes the next trusted-FIFO Agent request, or the reserved
   dummy AgentID when the queue is empty;
2. the PIR stage consumes the private row register produced by PSI in slot
   `j-1`, or the reserved dummy row;
3. only after PSI completes is the private register for slot `j+1` updated.

`run_fixed_schedule` derives every release time from one public origin plus the
slot ordinal. Completion of slot `j` never defines the planned time of slot
`j+1`; any inability to meet that absolute cadence is recorded as a capacity
failure rather than hidden by schedule drift.

Slot 0 therefore uses a dummy PIR bootstrap row. The final public slot uses a
dummy PSI input and drains the last prior PSI result through PIR. For a profile
with `R_A` total public slots, `R_A-1` slots can admit an already eligible real
request. A causally dependent Agent request learned only after its parent's PIR
can enter the next eligible PSI stage; the guaranteed serial retrieval depth is
`floor(R_A/2)` under the fixed schedule, not arbitrary depth.

## Private state and failure semantics

The trusted runtime retains only a FIFO request queue and:

```
previous_resolution = REAL_ROW(j) | DUMMY_ROW
```

AgentID, row index, hit/miss, queue occupancy, and artifact contents are absent
from the public projection. When capacity is exhausted the runtime raises
`PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED`; it never appends a slot. An
unprovisioned result schedules dummy PIR and queues repository retrieval into
the existing Gamma-controlled Trusted Gateway path. It does not open an
immediate Agent-specific connection.

## Preserved boundaries

- APSI: Microsoft APSI v0.13.1 at
  `548745efdb37b1d7d948c761a772488747ca16ab`.
- PIR: the existing real SimplePIR bridge and 100,001-row database (100,000
  artifacts plus one reserved dummy row).
- Wire shape per public slot: four APSI messages plus two SimplePIR messages,
  2,351,400 bytes total.
- Gateway: frozen V4R8 profile, 521 fixed cells of 1079-byte requests and
  800-byte responses; no Gateway timing code is called or modified by the
  Agent-access scheduler.
- Structural equivalence explicitly excludes realized timestamps and therefore
  is not a timing-privacy claim.

Implementation: `v15b_agent_access/pipeline.py`.
