# V12 duplex public timing virtualization — design freeze

Base attribution evidence:
`d22519ca1d8cce0c7fba5a9c3fa950a11bc8824b`.

This is an architectural development revision. The immutable P10 result remains
`EARLY_TIMING_DISTINGUISHABILITY` (6/10). No protected classifier campaign is
authorized in this phase.

## Forward request clock

The existing effective public request clock is unchanged:

```text
E_1 = D_1
E_i = max(D_i, S_(i-1) + Delta)
C_i = E_i - L_request
```

## Trusted Gateway response clock

For public slot `i`, let `A_i` be Gateway application receipt of the fixed-size
request, and `T_(i-1)` the previous actual public response release. With public
response lead `L_response = 5 ms`:

```text
N_i = E_i + L_response
F_1 = max(N_1, A_1 + L_response)
F_i = max(N_i, A_i + L_response, T_(i-1) + Delta)
G_i = F_i - L_response
```

At `G_i`, the trusted Gateway atomically commits a fixed-size RESULT if one was
eligible before the cutoff; otherwise it commits fixed-size WAIT. Encoding and
the transport write are bounded. Private readiness cannot move `F_i`, and a
late result remains queued for a later public slot.

## Open-loop Registry clock

The public Registry sender uses 100 opportunities, 60 ms period, a 5 ms
commitment lead, one fixed compute lane, and a public 100-entry in-flight bound:

```text
P_1 = O
P_j = max(O + (j-1)*60ms, U_(j-1) + 60ms)
K_j = P_j - 5ms
```

Real/dummy selection is frozen at `K_j`; an expired opportunity cannot be
filled retroactively. Sending never waits for an earlier response or framework
consumer. Registry answers use a conservative fixed public release clock:

```text
A_1 = P_1 + 50ms
A_j = max(P_j + 50ms, V_(j-1) + 60ms)
```

The input reader, one bounded computation lane, and ordered answer-release
lane are independent. Internal `answer_ready_ns` remains diagnostic-only.

## V4 public profiles

The V4 profile IDs are P10/P20/P25 with H4500, PIR60/Q100, fixed 1079-byte
requests and 800-byte responses. Their Relay cell counts remain respectively
506, 279, and 233. Statistical methodology is unchanged; all future protected
identities must be fresh.
