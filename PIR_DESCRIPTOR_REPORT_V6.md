# Encrypted descriptor SimplePIR results

All runs used official SimplePIR commit
`e9020b03bf2872c75b8954e749e32408b5db87ed`, real database construction, and
full preprocessing. All five queries per scale recovered and authenticated the
expected descriptor; repeated queries for the same index had different raw
query bytes; the server trace contained no private index, Agent name, logical
Agent ID, or route handle.

| Logical rows | Physical rows | Full preprocessing | Online query+answer+recovery | Upload+download | Client state | Peak allocation |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,000 | 42.427 ms | 0.709 ms | 8,612 B | 8,798,208 B | 39,759,872 B |
| 10,000 | 10,000 | 1,276.277 ms | 8.442 ms | 23,208 B | 23,740,416 B | 184,176,640 B |
| 100,000 | 100,001 | 34,409.406 ms | 52.240 ms | 73,568 B | 75,309,056 B | 1,347,020,800 B |

The 100K physical database is 102,401,024 bytes: exactly 100,000 logical rows
plus one 1,024-byte padding row required by the chosen parameters. Record
encryption took 3,535.901 ms. These are local-machine results, not deployment
SLA claims.
