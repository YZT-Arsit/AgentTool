# V11.1 HTTP/2 multiplexing

Canonical mode uses two loopback TLS HTTP/2 hops:

```text
trusted OHTTP client -- one HTTP/2 connection --> Relay
Relay                -- one HTTP/2 connection --> Gateway
```

Each public slot is one independent unary HTTP/2 stream.  The Relay forwards
only the OHTTP bytes and the public session/slot pair.  It records the actual
HTTP version and normalized connection reuse.  Canonical mode fails setup if
either hop does not negotiate HTTP/2.

The non-holdout fault fixture delays response stream 1 by 75 ms while the
public period remains 5 ms.  Later streams are launched before that response
returns, all 111 requests are issued, and the result can be carried by another
eligible slot.  This validates multiplexing and liveness, not traffic-analysis
resistance.
