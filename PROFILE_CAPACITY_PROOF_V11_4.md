# V11.4 profile capacity proof

Selected public profile: `V11_4-STRICT-ONLINE-H50-H3000-P10`.

The mechanically checked values are `M=50`, `H=3000 ms`, `Delta=10 ms`, `A=ceil(H/Delta)=300`, `B=50 ms`, `C=ceil(B/Delta)=5`, `D=M=50`, `T=1`, and `R=A+C+D+T=356`. The scheduled public lifetime is 3560 ms.

The runner admits no more than `M` operations and admits only before the public admission boundary. If all `M` operations are admission-ready before `H`, and every admitted external operation commits within `B`, the `C` completion rounds cover the last admitted provider operation and the following `D=M` pre-existing response slots can drain one result each. The terminal slot closes the fixed session. Unused requests are NOOP and unused responses are WAIT. No completion event adds a round, session, connection, or lifetime extension.

Per-session public cost is 356 OHTTP exchanges, 384124 request bytes, and 284800 response bytes at the Relay observation point, excluding lower-layer framing.
