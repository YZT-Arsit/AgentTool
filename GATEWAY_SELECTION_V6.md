# Gateway selection V6

The canonical choice remains CommonActionGateway V2: one persistent TCP
connection, fixed-size application cells, separate Worker and Pacer processes,
memory-mapped SPSC queues, no completion-triggered Pacer wake, fixed public
continuation slots, and zero dummy provider work. Deployment authentication is
specified as mutual TLS; the local experiment uses inner AEAD framing and local
TCP because no PKI is configured.

V6 adds an opaque cloud-client mode. Trusted code pre-encrypts request frames;
the cloud client receives neither the Gateway key nor the private workload and
returns only opaque response frames to the trusted consumer. Go protocol/unit
tests pass.

| Choice | V6 role |
|---|---|
| direct TLS | baseline; endpoint/count/order/timing remain visible |
| TCP/mTLS Gateway | canonical application/socket-boundary design |
| QUIC | future option, not implemented |
| SO_TXTIME/ETF datagram | future packet-timing extension, not implemented |

The sole new live V6 development arm used the opaque client, but delivered only
43/50 results. A second arm was blocked by Windows Application Control. Thus
Gateway protocol/function components pass, while the V6 live functional matrix
is `PARTIAL` and trajectory privacy is `OPEN`. Packet-level timing is open.
