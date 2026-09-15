# AgentID to labeled-PSI to SimplePIR mapping

## Canonical AgentID

The paper path uses one unsigned integer AgentID namespace. Real IDs satisfy
`0 <= AgentID < 2^63`; the high half of the 64-bit space is reserved for dummy
identifiers. Planner requests, artifact metadata, PSI items, and nested-Agent
references use this same logical ID.

## APSI item encoding

For a real AgentID `a`, the receiver and sender derive:

```
SHA-256("OAE-PROVISIONED-AGENT-ID-v1\0" || uint64_be(a))[0:16]
```

The 16-byte result is supplied as the Microsoft APSI item. Idle queries use a
separate domain, `OAE-IDLE-AGENT-ID-v1`, and the reserved value `2^64-1`, so
idle padding cannot collide with the real namespace. Python's built-in hash is
not used.

## Labeled result

The APSI label is a fixed 32-byte `PIRRowHandle`:

```
magic="OARH" | handle_version=1 | flags=0 |
uint64_be(row_index) | uint64_be(store_epoch) |
uint32_be(record_version=1) | reserved=0
```

It contains only the dense PIR address plus anti-staleness/version bindings;
it contains no Agent endpoint, route, or execution handle.

## Scale-store mapping

For scale AgentIDs `a in [1,100000]`, the evaluated dense permutation is:

```
j = ((a - 1) * 65537 + 17) mod 100000
```

Since `gcd(65537,100000)=1`, this is a bijection onto rows 0--99,999. Thus
`AgentID == PIR row` is false in general. APSI authenticates the returned row
handle through labeled PSI; after SimplePIR retrieval, AEAD decoding checks
that `artifact.canonical_agent_id == requested AgentID`. A mismatched,
replayed, stale, or malformed row fails closed.

